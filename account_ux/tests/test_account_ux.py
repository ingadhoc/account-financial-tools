import odoo.tests.common as common
from odoo import Command, fields


class TestAccountUXChangeCurrency(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.company_usd = self.env.ref('base.main_company')
        self.partner = self.env.ref('base.res_partner_12')

        self.currency_usd = self.env.ref('base.USD')
        self.currency_ars = self.env.ref('base.ARS')

        self.journal_usd = self.env.ref('account.1_sale')

        self.journal_ars = self.env['account.journal'].search([('company_id', '=', self.company_usd.id),
                                                              ('type', '=', 'sale'),
                                                              ('id', '!=', self.journal_usd.id)], limit=1)

        self.journal_ars.write({'currency_id': self.currency_ars})

    def test_account_ux_change_currency(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
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
            'journal_id': self.journal_ars
        })
        invoice.action_post()

        self.assertEqual(invoice.currency_id, self.journal_ars.currency_id,
                         "La moneda de la factura no está siendo modificada al cambiar el diario.")
