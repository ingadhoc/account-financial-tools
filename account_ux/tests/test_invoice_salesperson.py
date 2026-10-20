from odoo import Command
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestInvoiceSalesperson(TransactionCase):
    """Changing the customer on the form only sets the contact's salesperson on manual invoices."""

    def setUp(self):
        super().setUp()
        self.journal = self.env.ref("account.1_sale")
        self.user_1 = new_test_user(self.env, login="salesperson_1", groups="base.group_user")
        self.user_2 = new_test_user(self.env, login="salesperson_2", groups="base.group_user")
        self.partner_1 = self.env["res.partner"].create({"name": "Contact 1", "user_id": self.user_1.id})
        self.partner_2 = self.env["res.partner"].create({"name": "Contact 2", "user_id": self.user_2.id})

    def _invoice_form(self):
        return Form(
            self.env["account.move"].with_context(default_move_type="out_invoice", default_journal_id=self.journal.id)
        )

    def test_manual_invoice_follows_contact_salesperson(self):
        with self._invoice_form() as invoice_form:
            invoice_form.partner_id = self.partner_1
            invoice_form.partner_id = self.partner_2
        self.assertEqual(invoice_form.invoice_user_id, self.user_2)

    def test_invoice_with_origin_keeps_salesperson(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.journal.id,
                "partner_id": self.partner_2.id,
                "invoice_user_id": self.user_1.id,
                "invoice_origin": "SO001",
            }
        )
        with Form(invoice) as invoice_form:
            invoice_form.partner_id = self.partner_1
            invoice_form.partner_id = self.partner_2
        self.assertEqual(invoice.invoice_user_id, self.user_1)

    def _posted_manual_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.journal.id,
                "partner_id": self.partner_2.id,
                "invoice_user_id": self.user_1.id,
                "invoice_line_ids": [Command.create({"name": "Line", "quantity": 1, "price_unit": 100, "tax_ids": []})],
            }
        )
        invoice.action_post()
        return invoice

    def _reversal_wizard(self, invoice):
        return (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"journal_id": invoice.journal_id.id})
        )

    def test_refund_of_manual_invoice_keeps_salesperson(self):
        invoice = self._posted_manual_invoice()
        self._reversal_wizard(invoice).refund_moves()
        self.assertEqual(invoice.reversal_move_ids.invoice_user_id, self.user_1)

    def test_reverse_and_create_new_keeps_salesperson(self):
        invoice = self._posted_manual_invoice()
        wizard = self._reversal_wizard(invoice)
        wizard.modify_moves()
        self.assertEqual(invoice.reversal_move_ids.invoice_user_id, self.user_1)
        self.assertEqual(wizard.new_move_ids.invoice_user_id, self.user_1)
