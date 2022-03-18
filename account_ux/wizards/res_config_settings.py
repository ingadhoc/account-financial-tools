##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    sale_tax_ids = fields.Many2many(
        'account.tax',
        compute='_compute_tax_ids',
        inverse='_inverse_sale_tax_ids',
        string="Default Sale Taxes",
        help="This sale tax will be assigned by default on new products.",
    )
    purchase_tax_ids = fields.Many2many(
        'account.tax',
        compute='_compute_tax_ids',
        inverse='_inverse_purchase_tax_ids',
        string="Default Purchase Taxes",
        help="This purchase tax will be assigned by default on new products.",
    )

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
        ir_default = self.env['ir.default'].sudo()

        for rec in self:
            ir_default.set(
                'product.template',
                "taxes_id",
                rec.sale_tax_ids.ids,
                company_id=rec.company_id.id)
            sale_taxes = rec.sale_tax_ids.filtered(lambda tax: tax.company_id == rec.company_id)
            rec.company_id.account_sale_tax_id = sale_taxes[0] if sale_taxes else sale_taxes

    def _inverse_purchase_tax_ids(self):
        ir_default = self.env['ir.default'].sudo()

        for rec in self:
            ir_default.set(
                'product.template',
                "supplier_taxes_id",
                rec.purchase_tax_ids.ids,
                company_id=rec.company_id.id)

            purchase_taxes = rec.purchase_tax_ids.filtered(lambda tax: tax.company_id == rec.company_id)
            rec.company_id.account_purchase_tax_id = purchase_taxes[0] if purchase_taxes else purchase_taxes
