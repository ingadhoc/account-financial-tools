# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        manual_taxes = self.tax_line_ids.filtered(lambda x: x.manual)
        res = super(AccountInvoice, self)._onchange_invoice_line_ids()
        self.tax_line_ids += manual_taxes
        return res
