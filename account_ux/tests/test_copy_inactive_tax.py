from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCopyInactiveTax(TransactionCase):
    """Duplicating or reversing a document whose lines carry an archived tax."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.partner = self.env.ref("base.res_partner_12")
        self.journal = self.env.ref("account.1_sale")
        self.tax_group = self.env["account.tax.group"].create(
            {"name": "Test Group Inactive Tax", "company_id": self.company.id}
        )
        self.old_tax = self.env["account.tax"].create(
            {
                "name": "Old 21%",
                "amount_type": "percent",
                "amount": 21.0,
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
            }
        )

    def _create_invoice(self, tax):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "date": fields.Date.today(),
                "invoice_date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    Command.create(
                        {"name": "line", "quantity": 1, "price_unit": 100, "tax_ids": [Command.set(tax.ids)]}
                    )
                ],
            }
        )

    def _new_tax(self, **values):
        return self.env["account.tax"].create(
            {
                "name": "New 21%",
                "amount_type": "percent",
                "amount": 21.0,
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
                **values,
            }
        )

    def test_copy_replaces_archived_tax_by_its_active_twin(self):
        invoice = self._create_invoice(self.old_tax)
        new_tax = self._new_tax()
        self.old_tax.active = False

        copied = invoice.copy()

        self.assertEqual(copied.invoice_line_ids.tax_ids, new_tax)
        self.assertEqual(copied.amount_tax, invoice.amount_tax)

    def test_copy_drops_archived_tax_without_a_single_twin(self):
        invoice = self._create_invoice(self.old_tax)
        self._new_tax()
        self._new_tax(name="Another 21%")
        self.old_tax.active = False

        copied = invoice.copy()

        self.assertFalse(copied.invoice_line_ids.tax_ids)

    def test_copy_keeps_active_taxes_untouched(self):
        active_tax = self._new_tax()
        invoice = self._create_invoice(active_tax)

        copied = invoice.copy()

        self.assertEqual(copied.invoice_line_ids.tax_ids, active_tax)
