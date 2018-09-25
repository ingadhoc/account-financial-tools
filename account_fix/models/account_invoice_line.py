##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class AccountInvoiceLine(models.Model):

    _inherit = "account.invoice.line"

    @api.onchange('account_id')
    def _onchange_account_id(self):
        super(AccountInvoiceLine, self)._onchange_account_id()
        if not self.product_id:
            fpos = self.invoice_id.fiscal_position_id
            type_tax_use = self.invoice_id.type in (
                'out_invoice', 'out_refund') and 'sale' or 'purchase'
            self.invoice_line_tax_ids = fpos.map_tax(
                self.account_id.tax_ids.filtered(
                    lambda x: x.type_tax_use == type_tax_use),
                partner=self.partner_id).ids
