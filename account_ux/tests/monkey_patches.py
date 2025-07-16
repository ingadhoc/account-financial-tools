from odoo.addons.account_followup.tests.test_account_followup import TestAccountFollowupReports
from odoo import Command, fields
from freezegun import freeze_time

def monkey_patches():
    def test_followup_status_no_due_date(self):
        """
        Invoices without due date or pyament terms shouldn't be included in the calculation of followup reports.
        """
        self.followup_line = self.create_followup(delay=10)

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.from_string("2022-01-02"),
                "invoice_payment_term_id": False,
                "partner_id": self.partner_a.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "quantity": 1,
                            "price_unit": 500,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        date_due = invoice.invoice_date_due
        with freeze_time(date_due):
            self.assertPartnerFollowup(self.partner_a, "no_action_needed", self.followup_line)


    TestAccountFollowupReports.test_followup_status_no_due_date = test_followup_status_no_due_date
