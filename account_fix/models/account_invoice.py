# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, api


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None,
               date=None, description=None, journal_id=None):
        """
        En las facturas rectificativas no se calculan bien los impuestos (por)
        ej. el campo base. Esto arregla eso
        """
        new_invoices = super(AccountInvoice, self).refund(
            date_invoice=date_invoice, date=date,
            description=description, journal_id=journal_id)
        new_invoices.compute_taxes()
        return new_invoices
