import odoo.tests.common as common
from odoo import Command, fields


class TestAccountUXChangeCurrency(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.company_usd = self.env["res.company"].search([("currency_id.name", "=", "USD")], limit=1)
        self.partner_ri = self.env["res.partner"].search([], limit=1)

        self.currency_usd = self.env["res.currency"].search([("name", "=", "USD")])
        self.currency_ars = self.env["res.currency"].search([("name", "=", "ARS")])

        usd_journals = self.env["account.journal"].search(
            [("company_id", "=", self.company_usd.id), ("type", "=", "sale")], limit=2
        )

        self.journal_usd = usd_journals[0]
        self.journal_ars = usd_journals[1]
        self.journal_ars.write({"currency_id": self.currency_ars})

    def test_account_ux_change_currency(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_ri.id,
            'date': self.today,
            'move_type': 'out_invoice',
            'journal_id': self.journal_usd.id,
            'company_id': self.company_usd.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.env.ref('product.product_product_16').id,
                    'quantity': 1,
                    'price_unit': 1000,
                }),
            ],
        })
        invoice.write({
            'journal_id': self.journal_ars.id
        })
        invoice.action_post()

        self.assertEqual(
            invoice.currency_id,
            self.journal_ars.currency_id,
            "La moneda de la factura no está siendo modificada al cambiar el diario.",
        )
