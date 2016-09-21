# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
# from openerp import SUPERUSER_ID


class account_analytic_invoice_line(models.Model):
    _inherit = "account.analytic.invoice.line"

    tax_id = fields.Many2many(
        'account.tax',
        'analytic_account_tax',
        'analytic_accountr_line_id',
        'tax_id',
        'Taxes',
        domain="[('parent_id','=',False), ('company_id', '=', "
        "parent.company_id), ('type_tax_use','in', ['sale', 'all'])]",
    )

    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='', partner_id=False, price_unit=False, pricelist_id=False, company_id=None):
        result = super(account_analytic_invoice_line, self).product_id_change(
            product, uom_id, qty=qty, name=name, partner_id=partner_id, price_unit=price_unit, pricelist_id=pricelist_id, company_id=company_id)
        product = self.env['product.product'].browse(product)
        # if self._uid == SUPERUSER_ID and self._context.get('company_id'):
        #     taxes = product.taxes_id.filtered(
        #         lambda r: r.company_id.id == self._context['company_id'])
        # else:
        #     taxes = product.taxes_id
        taxes = product.taxes_id.filtered(
            lambda r: r.company_id.id == company_id)
        result['value']['tax_id'] = self.env[
            'account.fiscal.position'].map_tax(taxes)
        return result


class account_analytic_account(models.Model):
    _inherit = "account.analytic.account"

    @api.model
    def _prepare_invoice_line(self, line, fiscal_position):
        values = super(account_analytic_account, self)._prepare_invoice_line(
            line, fiscal_position)
        values['invoice_line_tax_id'] = [(6, 0, line.tax_id.ids)]
        return values
