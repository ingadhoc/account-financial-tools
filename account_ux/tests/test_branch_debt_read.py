# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestBranchDebtRead(AccountTestInvoicingCommon):
    """A user working in one branch reads the debt of the other branches of the group
    when the root does not block inter-company reconciliation, and only reads it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root_company = cls.company_data["company"]
        cls.root_company.write(
            {
                "block_intercompany_conciliation": "none",
                "child_ids": [
                    Command.create({"name": "Branch A"}),
                    Command.create({"name": "Branch B"}),
                ],
            }
        )
        cls.cr.precommit.run()  # load the CoA
        cls.branch_a, cls.branch_b = cls.root_company.child_ids

        cls.invoice_b = cls.init_invoice("out_invoice", amounts=[1000.0], company=cls.branch_b, post=True)
        cls.misc_b = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "company_id": cls.branch_b.id,
                "journal_id": cls.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create({"account_id": cls.company_data["default_account_revenue"].id, "balance": 100.0}),
                    Command.create({"account_id": cls.company_data["default_account_expense"].id, "balance": -100.0}),
                ],
            }
        )
        cls.misc_b.action_post()

        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Branch A accountant",
                "login": "branch_a_accountant",
                "company_id": cls.branch_a.id,
                "company_ids": [Command.set(cls.branch_a.ids)],
                "group_ids": [
                    Command.set(
                        (
                            cls.env.ref("account.group_account_manager")
                            + cls.env.ref("account_ux.group_read_branch_debt")
                        ).ids
                    )
                ],
            }
        )

    def _as_user_a(self, records):
        return records.with_user(self.user_a).with_context(allowed_company_ids=self.branch_a.ids)

    def test_reads_other_branch_debt(self):
        invoice = self._as_user_a(self.invoice_b)
        invoice.check_access("read")
        invoice.line_ids.check_access("read")
        self.assertTrue(invoice.amount_residual)
        receivable = self._as_user_a(self.env["account.move.line"]).search(
            [("partner_id", "=", self.partner_a.id), ("account_type", "=", "asset_receivable")]
        )
        self.assertIn(self.invoice_b.line_ids.filtered(lambda l: l.account_type == "asset_receivable"), receivable)

    def _sibling_journal(self):
        return self.env["account.journal"].create(
            {"name": "Sales B", "code": "ZSB", "type": "sale", "company_id": self.branch_b.id}
        )

    def test_reads_the_journal_of_a_sibling_branch_without_finding_it(self):
        journal = self._sibling_journal()
        self.env.invalidate_all()
        self.assertEqual(self._as_user_a(journal).name, "Sales B")
        journals = self._as_user_a(self.env["account.journal"])
        self.assertNotIn(journal, journals.search([]))
        self.assertFalse(journals.search_count([("id", "=", journal.id)]))

    def test_the_invoice_of_another_branch_opens_without_the_reset_button(self):
        invoice = self._as_user_a(self.invoice_b)
        self.assertEqual(Form(invoice).partner_id, self.partner_a)
        self.assertFalse(invoice.show_reset_to_draft_button)

    def test_without_the_group_other_branches_stay_hidden(self):
        journal = self._sibling_journal()
        self.user_a.group_ids -= self.env.ref("account_ux.group_read_branch_debt")
        with self.assertRaises(AccessError):
            self._as_user_a(self.invoice_b).check_access("read")
        with self.assertRaises(AccessError):
            self._as_user_a(journal).check_access("read")

    def test_cannot_write_other_branch_debt(self):
        with self.assertRaises(AccessError):
            self._as_user_a(self.invoice_b).write({"ref": "changed"})

    def test_entries_without_debt_stay_hidden(self):
        with self.assertRaises(AccessError):
            self._as_user_a(self.misc_b).check_access("read")
        with self.assertRaises(AccessError):
            self._as_user_a(self.misc_b.line_ids).check_access("read")

    def test_blocked_reconciliation_hides_other_branches(self):
        self.root_company.block_intercompany_conciliation = "all"
        with self.assertRaises(AccessError):
            self._as_user_a(self.invoice_b).check_access("read")
        with self.assertRaises(AccessError):
            self._as_user_a(self.invoice_b.line_ids).check_access("read")

    def test_blocked_between_legal_entities_reads_only_its_own_entity(self):
        """Sin CUIT cada sucursal es su propia entidad fiscal; con el mismo CUIT, se ven."""
        self.root_company.block_intercompany_conciliation = "other_legal_entity"
        with self.assertRaises(AccessError):
            self._as_user_a(self.invoice_b).check_access("read")

        companies = self.root_company + self.branch_a + self.branch_b
        companies.country_id = False
        companies.vat = "30111111118"
        self._as_user_a(self.invoice_b).check_access("read")
