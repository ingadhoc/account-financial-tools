import odoo.tests.common as common
from odoo.tests import tagged
from odoo import Command, fields
from datetime import timedelta


class TestAccountPaymentTermSurcharge(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.first_company = self.env['res.company'].search([('name', '=', 'Muebleria US')], limit=1)
        self.partner_ri = self.env['res.partner'].search([('name', '=', 'ADHOC SA')], limit=1)
        self.first_company_journal = self.env.ref('account.1_sale')

        self.product_surcharge = self.env.ref('product.product_product_16')
        self.env['res.config.settings'].search([('company_id', '=', self.first_company.id)]).payment_term_surcharge_product_id = self.product_surcharge.id

        self.payment_term = self.env['account.payment.term'].create({
            'name': 'Test payment term'
        })

        self.surcharge = self.env['account.payment.term.surcharge'].create({
            'surcharge': 10,
            'days': 1,
            'payment_term_id': self.payment_term.id,
            'option': 'day_after_invoice_date',
            'day_of_the_month': 0
        })

    @tagged("-at_install", "post_install",)
    def test_payment_term_surcharge(self):
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_ri.id,
            'invoice_date': self.today - timedelta(days=1),
            'invoice_date_due': self.today,
            'move_type': 'out_invoice',
            'journal_id': self.first_company_journal.id,
            'company_id': self.first_company.id,
            'invoice_payment_term_id': self.payment_term.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.env.ref('product.product_product_16').id,
                    'quantity': 1,
                    'price_unit': 1000,
                }),
            ]
        })
        invoice.avoid_surcharge_invoice = False
        invoice.action_post()

        invoice._cron_recurring_surcharges_invoices()
        self.assertFalse(invoice.next_surcharge_date, "La proxima fecha de recargo no es la correspondiente ")
        self.assertEqual(invoice.debit_note_ids[0].amount_total, invoice.amount_total / self.surcharge.surcharge, "Fallo el monto de la ND por el recargo")
