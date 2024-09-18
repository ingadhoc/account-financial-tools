import odoo.tests.common as common
from odoo import Command, fields


class TestAccountUXChangeCurrency(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.first_company = self.env['res.company'].search([], limit=1)
        self.partner_ri = self.env['res.partner'].search([], limit=1)

        self.currency_usd = self.env['res.currency'].search([('name', '=', 'USD')])
        self.currency_ars = self.env['res.currency'].search([('name', '=', 'ARS'), ('active', 'in', [False])])
        self.currency_ars.active = True

        self.first_company_journal_usd = self.env['account.journal'].search([('company_id', '=', self.first_company.id), ('type', '=', 'sale')], limit=1)
        self.first_company_journal_ars = self.env['account.journal'].create({
            'name': 'ARS sale journal',
            'company_id': self.first_company.id,
            'type': 'sale',
            'currency_id': self.currency_ars.id,
            'code': 'ARS'
        })

    def test_account_ux_change_currency(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_ri.id,
            'date': self.today,
            'move_type': 'out_invoice',
            'journal_id': self.first_company_journal_usd.id,
            'company_id': self.first_company.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.env.ref('product.product_product_16').id,
                    'quantity': 1,
                    'price_unit': 1000,
                }),
            ],
        })
        invoice.write({
            'journal_id': self.first_company_journal_ars.id
        })
        invoice.action_post()

        self.assertEqual(invoice.currency_id, self.first_company_journal_ars.currency_id, "La moneda de la factura no esta siendo modificada al cambiar el diario.")
