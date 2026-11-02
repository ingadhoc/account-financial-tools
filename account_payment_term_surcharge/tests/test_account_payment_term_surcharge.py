from datetime import timedelta

from odoo import Command, fields
from odoo.tests import common, tagged


class TestAccountPaymentTermSurcharge(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.first_company = self.env.ref("base.main_company")
        self.partner_ri = self.env["res.partner"].search([], limit=1)
        self.first_company_journal = self.env["account.journal"].search(
            [("company_id", "=", self.first_company.id), ("type", "=", "sale")]
        )

        self.product_surcharge = self.env.ref("product.product_product_16")
        self.first_company.payment_term_surcharge_product_id = self.product_surcharge.id
        self.payment_term = self.env["account.payment.term"].create({"name": "Test payment term"})

        self.surcharge = self.env["account.payment.term.surcharge"].create(
            {
                "surcharge": 10,
                "days": 1,
                "payment_term_id": self.payment_term.id,
                "option": "day_after_invoice_date",
                "day_of_the_month": 0,
            }
        )

    @tagged(
        "-at_install",
        "post_install",
    )
    def test_payment_term_surcharge(self):
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner_ri.id,
                "invoice_date": self.today - timedelta(days=1),
                "invoice_date_due": self.today,
                "move_type": "out_invoice",
                "journal_id": self.first_company_journal.id,
                "company_id": self.first_company.id,
                "invoice_payment_term_id": self.payment_term.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.env.ref("product.product_product_16").id,
                            "quantity": 1,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )
        invoice.action_post()
        invoice.avoid_surcharge_invoice = False

        invoice._cron_recurring_surcharges_invoices()
        self.assertFalse(invoice.next_surcharge_date, "La proxima fecha de recargo no es la correspondiente ")
        self.assertEqual(
            abs(invoice.debit_note_ids[0].invoice_line_ids.balance),
            invoice.amount_total / self.surcharge.surcharge,
            "Fallo el monto de la ND por el recargo",
        )

    def _create_posted_invoice(self, invoice_date):
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner_ri.id,
                "invoice_date": invoice_date,
                "move_type": "out_invoice",
                "journal_id": self.first_company_journal.id,
                "company_id": self.first_company.id,
                "invoice_payment_term_id": self.payment_term.id,
                "invoice_line_ids": [Command.create({"product_id": self.product_surcharge.id, "price_unit": 1000})],
            }
        )
        invoice.action_post()
        return invoice

    def _run_cron(self, times=1):
        for _i in range(times):
            self.env["account.move"]._cron_recurring_surcharges_invoices()

    def _create_debit_note(self, invoice, date):
        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"date": date, "reason": "Manual"})
        )
        return self.env["account.move"].browse(wizard.create_debit()["res_id"])

    def test_rule_change_does_not_charge_twice(self):
        invoice_date = self.today - timedelta(days=20)
        invoice = self._create_posted_invoice(invoice_date)
        self.surcharge.days = 5
        self._run_cron()
        self.assertEqual(invoice.debit_note_ids.surcharge_id, self.surcharge)

        self.surcharge.days = 4
        self._run_cron(times=2)
        self.assertEqual(len(invoice.debit_note_ids), 1)
        self.assertFalse(invoice.next_surcharge_date)

        new_invoice = self._create_posted_invoice(invoice_date)
        self.assertEqual(new_invoice.next_surcharge_date, invoice_date + timedelta(days=4))

    def test_two_rules_same_day(self):
        second = self.surcharge.copy({"surcharge": 5})
        invoice = self._create_posted_invoice(self.today - timedelta(days=5))
        self._run_cron(times=3)
        self.assertEqual(len(invoice.debit_note_ids), 2)
        self.assertEqual(invoice.debit_note_ids.surcharge_id, self.surcharge | second)
        self.assertEqual(set(invoice.debit_note_ids.mapped("invoice_date")), {self.today - timedelta(days=4)})

    def test_draft_edit_delete_and_cancel(self):
        invoice = self._create_posted_invoice(self.today - timedelta(days=5))
        self._run_cron()
        note = invoice.debit_note_ids
        self.assertEqual(note.state, "draft")

        note.invoice_date = self.today - timedelta(days=1)
        self._run_cron()
        self.assertEqual(invoice.debit_note_ids, note)

        note.unlink()
        self._run_cron()
        note = invoice.debit_note_ids
        self.assertEqual(note.surcharge_id, self.surcharge)

        note.button_cancel()
        self._run_cron()
        self.assertEqual(invoice.debit_note_ids, note)

    def test_other_debit_notes(self):
        invoice_date = self.today - timedelta(days=5)
        surcharge_date = invoice_date + timedelta(days=1)

        # A debit note that is not a surcharge does not count as charged
        invoice = self._create_posted_invoice(invoice_date)
        manual_note = self._create_debit_note(invoice, surcharge_date)
        self._run_cron()
        self.assertEqual(len(invoice.debit_note_ids), 2)
        self.assertEqual((invoice.debit_note_ids - manual_note).surcharge_id, self.surcharge)

        # A surcharge debit note created before surcharge_id existed is matched by date
        legacy_invoice = self._create_posted_invoice(invoice_date)
        legacy_note = self._create_debit_note(legacy_invoice, surcharge_date)
        legacy_note.invoice_line_ids = [Command.create({"product_id": self.product_surcharge.id, "price_unit": 100})]
        self._run_cron()
        self.assertEqual(legacy_invoice.debit_note_ids, legacy_note)

    def test_rule_change_warning(self):
        def onchange_warning():
            rule = self.env["account.payment.term.surcharge"].new({"days": 2}, origin=self.surcharge)
            return (rule._onchange_surcharge_rule() or {}).get("warning")

        self.assertFalse(onchange_warning())
        invoice = self._create_posted_invoice(self.today - timedelta(days=5))
        self._run_cron()
        self.assertTrue(onchange_warning())
        invoice.debit_note_ids.button_cancel()
        self.assertFalse(onchange_warning())
