##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class AccountInvoiceRefund(models.TransientModel):
    _inherit = 'account.invoice.refund'

    @api.multi
    def compute_refund(self, mode='refund'):
        res = super(AccountInvoiceRefund, self).compute_refund(mode=mode)
        # We force to change the commercial after the new invoice of the refund was created
        if res and res.get('domain', False):
            invoices = self.env['account.invoice'].browse(res['domain'][1][2])
            for inv in invoices.filtered(lambda i: i.type == 'out_invoice'):
                inv._onchange_partner_commercial()
        return res
