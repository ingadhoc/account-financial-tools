# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHistoricalCostBranches(TransactionCase):
    """Branch selling a product whose valuation lives in the parent company.

    Data is created by hand (no chart of accounts, no demo data) so the test
    runs both on a minimal database and on a full OBA one, same as the
    `stock_account_multicompany_ux` suite it mirrors.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env["ir.module.module"].search(
            [("name", "=", "stock_account_multicompany_ux"), ("state", "=", "installed")]
        ):
            raise cls.skipTest(cls, "stock_account_multicompany_ux must be installed")

        cls.parent_company = cls.env["res.company"].create({"name": "Parent Co HC"})
        cls.branch_company = cls.env["res.company"].create({"name": "Branch Co HC", "parent_id": cls.parent_company.id})
        cls.env.user.company_ids = [Command.link(cls.parent_company.id), Command.link(cls.branch_company.id)]
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=[cls.branch_company.id, cls.parent_company.id])
        )

        cls.account_receivable = cls._create_account("ARHC", "Receivable", "asset_receivable")
        cls.account_income = cls._create_account("INHC", "Income", "income")
        cls.account_expense = cls._create_account("EXHC", "Expense", "expense")
        cls.account_stock_valuation = cls._create_account("SVHC", "Stock Valuation", "asset_current")

        cls.journal_sale = (
            cls.env["account.journal"]
            .with_company(cls.parent_company)
            .create(
                {
                    "name": "Sales HC",
                    "code": "SAHC",
                    "type": "sale",
                    "company_id": cls.parent_company.id,
                    "default_account_id": cls.account_income.id,
                }
            )
        )
        cls.journal_stock = (
            cls.env["account.journal"]
            .with_company(cls.parent_company)
            .create({"name": "Stock HC", "code": "STHC", "type": "general", "company_id": cls.parent_company.id})
        )

        cls.categ = (
            cls.env["product.category"]
            .with_company(cls.parent_company)
            .create(
                {
                    "name": "Shared Standard HC",
                    "property_cost_method": "standard",
                    "property_valuation": "real_time",
                    "shared_to_branches": True,
                    "property_account_income_categ_id": cls.account_income.id,
                    "property_account_expense_categ_id": cls.account_expense.id,
                    "property_stock_valuation_account_id": cls.account_stock_valuation.id,
                    "property_stock_journal": cls.journal_stock.id,
                }
            )
        )

        cls.product = (
            cls.env["product.product"]
            .with_company(cls.parent_company)
            .create(
                {
                    "name": "Product HC",
                    "is_storable": True,
                    "categ_id": cls.categ.id,
                    "standard_price": 100.0,
                }
            )
        )

        # The branch keeps its own cost (standard_price is company dependent):
        # 40 against the parent's 100. Stock moves on the branch side are valued
        # at 40, which is the divergence under test.
        cls.product.with_company(cls.branch_company).standard_price = 40.0
        cls._receive(cls.parent_company, 10, 100.0)
        cls._receive(cls.branch_company, 10, 40.0)

        cls.partner = cls.env["res.partner"].create({"name": "Customer HC"})
        for company in (cls.parent_company, cls.branch_company):
            cls.partner.with_company(company).property_account_receivable_id = cls.account_receivable

    @classmethod
    def _create_account(cls, code, name, account_type):
        return (
            cls.env["account.account"]
            .with_company(cls.parent_company)
            .create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "company_ids": [Command.link(cls.parent_company.id)],
                }
            )
        )

    @classmethod
    def _warehouse(cls, company):
        return cls.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)

    @classmethod
    def _receive(cls, company, quantity, unit_cost):
        move = (
            cls.env["stock.move"]
            .with_company(company)
            .create(
                {
                    "product_id": cls.product.id,
                    "product_uom_qty": quantity,
                    "location_id": cls.env.ref("stock.stock_location_suppliers").id,
                    "location_dest_id": cls._warehouse(company).lot_stock_id.id,
                    "company_id": company.id,
                    "price_unit": unit_cost,
                }
            )
        )
        move._action_confirm()
        move.quantity = quantity
        move.picked = True
        move._action_done()
        return move

    def _deliver(self, company, quantity):
        move = (
            self.env["stock.move"]
            .with_company(company)
            .create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": quantity,
                    "location_id": self._warehouse(company).lot_stock_id.id,
                    "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                    "company_id": company.id,
                }
            )
        )
        move._action_confirm()
        move.quantity = quantity
        move.picked = True
        move._action_done()
        return move

    def _branch_invoice(self, quantity=3.0):
        return (
            self.env["account.move"]
            .with_company(self.branch_company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": self.branch_company.id,
                    "partner_id": self.partner.id,
                    "journal_id": self.journal_sale.id,
                    "invoice_date": "2026-01-15",
                    "invoice_date_due": "2026-01-15",
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": quantity,
                                "price_unit": 150.0,
                                "tax_ids": [Command.clear()],
                            }
                        )
                    ],
                }
            )
        )

    def test_branch_freezes_the_parent_cost(self):
        """The branch cost (40) must never be the one frozen: the parent's (100)
        is what the core posts as COGS, before and after the delivery."""
        invoice = self._branch_invoice(quantity=3)
        invoice.action_post()
        line = invoice.line_ids.filtered(lambda line: line.display_type == "product")

        with self.subTest("invoiced before delivering: provisional, at the parent cost"):
            self.assertTrue(line.historical_cost_provisional)
            self.assertAlmostEqual(line.historical_cost, 3 * 100.0)

        out_move = self._deliver(self.branch_company, 3)
        self.assertAlmostEqual(out_move.value, 3 * 40.0)
        line._complete_historical_cost_from_moves(out_move)

        with self.subTest("completed on delivery: real, still at the parent cost"):
            self.assertFalse(line.historical_cost_provisional)
            self.assertAlmostEqual(line.historical_cost, 3 * 100.0)
