from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

LOGGER = "odoo.addons.account_interests.models.res_company_interest"


@tagged("post_install", "-at_install")
class TestAccountInterests(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.to_date = fields.Date.today()
        cls.from_date = cls.to_date - relativedelta(days=30)
        cls.partner_1, cls.partner_2 = cls.env["res.partner"].create(
            [{"name": "Interest partner 1"}, {"name": "Interest partner 2"}]
        )
        cls.interest_product = cls.env["product.product"].create(
            {"name": "Interest", "type": "service", "list_price": 0.0, "taxes_id": [Command.clear()]}
        )
        cls.rule = cls.env["res.company.interest"].create(
            {
                "company_id": cls.company.id,
                "receivable_account_ids": [Command.set(cls.company_data["default_account_receivable"].ids)],
                "interest_product_id": cls.interest_product.id,
                "rate": 0.3,
                "past_due_rate": 0.2,
                "rule_type": "monthly",
                "interval": 1,
                "next_date": cls.to_date,
            }
        )
        # keep the demo rules out of the cron runs
        cls.env["res.company.interest"].search([("id", "!=", cls.rule.id)]).write(
            {"next_date": cls.to_date + relativedelta(days=1)}
        )

    def setUp(self):
        super().setUp()
        # the model commits between batches, which the test cursor forbids
        self.patch(self.env.cr, "commit", lambda: None)

    def _create_invoice(self, partner, due_date, amount=1000.0):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": due_date,
                "invoice_date_due": due_date,
                "invoice_line_ids": [
                    Command.create({"name": "Line", "quantity": 1, "price_unit": amount, "tax_ids": [Command.clear()]})
                ],
            }
        )
        move.action_post()
        return move

    def _pay(self, invoice, payment_date):
        self.env["account.payment.register"].with_context(active_model="account.move", active_ids=invoice.ids).create(
            {"payment_date": payment_date, "amount": invoice.amount_residual}
        ).action_create_payments()

    def _interest_invoices(self, partner):
        return self.env["account.move"].search(
            [("partner_id", "=", partner.id), ("invoice_origin", "=", "Interests Invoice")]
        )

    def test_01_last_period_debt(self):
        # 10 overdue days inside the period: 1000 * 10 * 0.3 / 30
        self._create_invoice(self.partner_1, self.to_date - relativedelta(days=10))
        debt = self.rule._calculate_debts(self.from_date, self.to_date)
        values = debt[self.partner_1]["values"]
        self.assertAlmostEqual(values["Deuda último periodo"], 100.0)
        self.assertNotIn("Deuda periodos anteriores", values)
        self.assertEqual(len(debt[self.partner_1]["details"]), 1)

    def test_02_previous_periods_debt(self):
        # due before the period: residual * past_due_rate * interval
        self._create_invoice(self.partner_1, self.from_date - relativedelta(days=5))
        values = self.rule._calculate_debts(self.from_date, self.to_date)[self.partner_1]["values"]
        self.assertAlmostEqual(values["Deuda periodos anteriores"], 200.0)
        self.assertNotIn("Deuda último periodo", values)

    def test_03_late_payment_interest(self):
        invoice = self._create_invoice(self.partner_1, self.from_date + relativedelta(days=5))
        self._pay(invoice, self.from_date + relativedelta(days=15))
        # without the option a fully paid invoice generates nothing
        self.assertNotIn(self.partner_1, self.rule._calculate_debts(self.from_date, self.to_date))
        # 10 days late: 1000 * 10 * 0.3 / 30
        self.rule.late_payment_interest = True
        values = self.rule._calculate_debts(self.from_date, self.to_date)[self.partner_1]["values"]
        self.assertAlmostEqual(values["Deuda pagos vencidos"], 100.0)

    def test_04_create_invoices_automatic_validation(self):
        self._create_invoice(self.partner_1, self.to_date - relativedelta(days=10))
        self.rule.create_invoices(self.from_date, self.to_date)
        interest = self._interest_invoices(self.partner_1)
        self.assertEqual(len(interest), 1)
        self.assertEqual(interest.state, "posted")
        self.assertEqual(interest.invoice_line_ids.product_id, self.interest_product)
        self.assertAlmostEqual(interest.amount_total, 100.0)
        self.assertIn("Residual", interest.message_ids[:1].body)

        # no automatic validation: the invoice stays in draft
        self.rule.automatic_validation = False
        self._create_invoice(self.partner_2, self.to_date - relativedelta(days=10))
        self.rule.create_invoices(self.from_date, self.to_date)
        self.assertEqual(self._interest_invoices(self.partner_2).state, "draft")

    def test_05_partner_not_invoiced_twice(self):
        self._create_invoice(self.partner_1, self.to_date - relativedelta(days=10))
        self.rule.create_invoices(self.from_date, self.to_date)
        self.rule.create_invoices(self.from_date, self.to_date)
        self.assertEqual(len(self._interest_invoices(self.partner_1)), 1)

    def test_06_prepare_invoice_skips_non_positive_debt(self):
        journal = self.company_data["default_journal_sale"]
        for debt in ({}, {"Deuda último periodo": 0.0}, {"Deuda periodos anteriores": -50.0}):
            self.assertFalse(self.rule._prepare_interest_invoice(self.partner_1, debt, self.to_date, journal))
        vals = self.rule._prepare_interest_invoice(
            self.partner_1, {"Deuda último periodo": 100.0, "Deuda periodos anteriores": 0.0}, self.to_date, journal
        )
        self.assertEqual(vals["journal_id"], journal.id)
        self.assertEqual(len(vals["invoice_line_ids"]), 1)
        self.assertEqual(vals["invoice_line_ids"][0][2]["price_unit"], 100.0)

    def test_07_next_date_and_cron(self):
        self.rule.write({"rule_type": "weekly", "interval": 2})
        self.rule.create_interest_invoices()
        self.assertEqual(self.rule.next_date, self.to_date + relativedelta(weeks=2))

        # the cron only runs due rules
        self.rule.next_date = self.to_date
        self.env["res.company.interest"]._cron_recurring_interests_invoices()
        self.assertEqual(self.rule.next_date, self.to_date + relativedelta(weeks=2))
        self.env["res.company.interest"]._cron_recurring_interests_invoices()
        self.assertEqual(self.rule.next_date, self.to_date + relativedelta(weeks=2))

    def test_08_additional_domain(self):
        self._create_invoice(self.partner_1, self.to_date - relativedelta(days=10))
        self._create_invoice(self.partner_2, self.to_date - relativedelta(days=10))
        self.rule.domain = "[('partner_id', '=', %d)]" % self.partner_1.id
        debt = self.rule._calculate_debts(self.from_date, self.to_date)
        self.assertIn(self.partner_1, debt)
        self.assertNotIn(self.partner_2, debt)

    def test_09_failed_validation_keeps_draft_and_logs(self):
        self._create_invoice(self.partner_1, self.to_date - relativedelta(days=10))
        self._create_invoice(self.partner_2, self.to_date - relativedelta(days=10))
        with (
            patch.object(type(self.env["account.move"]), "action_post", side_effect=UserError("boom")),
            self.assertLogs(LOGGER, level="ERROR") as logs,
        ):
            self.rule.create_invoices(self.from_date, self.to_date)
        self.assertIn("boom", logs.output[0])
        # the error is only logged: both invoices stay in draft and the run continues
        for partner in (self.partner_1, self.partner_2):
            self.assertEqual(self._interest_invoices(partner).state, "draft")
