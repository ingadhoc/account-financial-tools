##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api
import odoo.addons.decimal_precision as dp


class AccountInvoiceTaxWizard(models.TransientModel):
    _name = 'account.invoice.tax.wizard'
    _description = 'Account Invoice Tax Wizard'

    @api.model
    def _get_invoice(self):
        return self._context.get('active_id', False)

    tax_id = fields.Many2one(
        'account.tax',
        'Tax',
        required=True,
    )
    name = fields.Char(
        'Tax Description',
        required=True,
    )
    amount = fields.Float(
        digits=dp.get_precision('Account'),
        required=True,
    )
    invoice_id = fields.Many2one(
        'account.invoice',
        'Invoice',
        default=_get_invoice,
    )
    base = fields.Float(
        digits=dp.get_precision('Account'),
        help='Not stored, only used to suggest amount',
    )
    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        'Analytic Account',
    )
    invoice_type = fields.Selection(
        related='invoice_id.type',
        string='Invoice Type',
        readonly=True,
    )
    invoice_company_id = fields.Many2one(
        'res.company',
        'Company',
        related='invoice_id.company_id',
        readonly=True,
    )

    @api.onchange('invoice_id')
    def onchange_invoice(self):
        self.base = self.invoice_id.amount_untaxed

    @api.onchange('tax_id')
    def onchange_tax(self):
        res = self.tax_id.compute_all(self.base)
        self.name = res.get('taxes', False) and res['taxes'][0].get(
            'name', False) or False

    @api.onchange('base', 'tax_id')
    def onchange_base(self):
        res = self.tax_id.compute_all(self.base)
        self.amount = res.get('taxes', False) and res['taxes'][0].get(
            'amount', False) or False

    @api.multi
    def confirm(self):
        self.ensure_one()
        if not self.invoice_id or not self.tax_id:
            return False
        invoice = self.invoice_id
        res = self.tax_id.compute_all(self.base)
        tax = res['taxes'][0]
        val = {
            'invoice_id': invoice.id,
            'name': self.name,
            'tax_id': self.tax_id.id,
            'amount': self.amount,
            'manual': True,
            'sequence': 99,
            'account_analytic_id': self.account_analytic_id.id,
            'account_id': invoice.type in ('out_invoice', 'in_invoice') and (
                tax['account_id'] or False) or (
                tax['refund_account_id'] or False),
        }
        self.env['account.invoice.tax'].create(val)
