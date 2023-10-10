##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    reconcile_on_company_currency = fields.Boolean(
        related='company_id.reconcile_on_company_currency', readonly=False)
    sale_tax_ids = fields.Many2many(
        'account.tax',
        compute='_compute_tax_ids',
        inverse='_inverse_sale_tax_ids',
        string="Default Sale Taxes",
        help="This sale tax will be assigned by default on new products.",)
    purchase_tax_ids = fields.Many2many(
        'account.tax',
        compute='_compute_tax_ids',
        inverse='_inverse_purchase_tax_ids',
        string="Default Purchase Taxes",
        help="This purchase tax will be assigned by default on new products.",)

    @api.depends('company_id')
    def _compute_tax_ids(self):

        ir_default = self.env['ir.default'].sudo()
        for rec in self:
            company_id = rec.company_id.id

            taxes_ids = ir_default.get('product.template', 'taxes_id', company_id=company_id) or \
                rec.company_id.account_sale_tax_id.ids
            supplier_taxes_ids = ir_default.get('product.template', 'supplier_taxes_id', company_id=company_id) or \
                rec.company_id.account_purchase_tax_id.ids

            rec.sale_tax_ids = taxes_ids
            rec.purchase_tax_ids = supplier_taxes_ids

    def _inverse_sale_tax_ids(self):
        for rec in self:
            rec._set_default_tax('sale', rec.sale_tax_ids, rec.company_id)

    def _inverse_purchase_tax_ids(self):
        for rec in self:
            rec._set_default_tax('purchase', rec.purchase_tax_ids, rec.company_id)

    @api.model
    def _set_default_tax(self, type_tax_use, taxes, company):
        """ Creamos este metodo para no duplicar tanto codigo y ademas para poder llamarlo desde chart template sin
        necesidad de instancear un res.config.settings"""
        ir_default = self.env['ir.default'].sudo()
        if type_tax_use == 'sale':
            product_field = 'taxes_id'
            company_field = 'account_sale_tax_id'
        elif type_tax_use == 'purchase':
            product_field = 'supplier_taxes_id'
            company_field = 'account_purchase_tax_id'
        else:
            raise ValidationError('type_tax_use %s is invalid, possible values are "sale" or "purchase"')
        ir_default.set(
            'product.template',
            product_field,
            taxes.ids,
            company_id=company.id)
        company_taxes = taxes.filtered(lambda tax: tax.company_id == company)
        company.write({company_field: company_taxes[:1]})
        if company_taxes:
            # seteamos este impuesto por defecto a todos los productos de esta compañía o que o tengan compañía y
            # que no tengan ningun impuesto de esta compania ya configurado
            all_company_taxes = self.env['account.tax'].search(
                [('type_tax_use', '=', type_tax_use), ('company_id', '=', company.id)])
            self.env['product.template'].search([
                ('company_id', 'in', [False, company.id]),
                (product_field, 'not in', all_company_taxes.ids)]).write({product_field: [(4, company_taxes[0].id)]})
