# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models


class AccountInvoiceLine(models.Model):

    _inherit = "account.invoice.line"

    # we override this method because need use product currency
    #  instead the invoice currency.
    # This PR to odoo explain more clearly
    # https://github.com/odoo/odoo/pull/25237
    def _set_currency(self):
        currency = self.invoice_id.currency_id
        if self.product_id and currency:
            if self.product_id.currency_id != currency:
                self.price_unit = self.price_unit * currency.with_context(
                    dict(self._context or {},
                         date=self.invoice_id.date_invoice)).rate
