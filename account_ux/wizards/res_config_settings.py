##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    sale_tax_ids = fields.Many2many(
        'account.tax',
        'config_tax_default_rel',
        'account_id', 'tax_id',
        string="Default Sale Taxes",
        help="This sale tax will be assigned by default on new products.",
    )
    purchase_tax_ids = fields.Many2many(
        'account.tax',
        'config_purchase_tax_default_rel',
        'account_id', 'purchase_tax_id',
        string="Default Purchase Taxes",
        help="This purchase tax will be assigned by default on new products.",
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()

        company_id = self.company_id.id or self.env.company.id
        ir_default = self.env['ir.default'].sudo()

        taxes_ids = ir_default.get(
            'product.template', 'taxes_id', company_id=company_id)
        supplier_taxes_ids = ir_default.get(
            'product.template', 'supplier_taxes_id',
            company_id=company_id)

        res.update({
            'sale_tax_ids': [(6, 0, taxes_ids)],
            'purchase_tax_ids': [(6, 0, supplier_taxes_ids)],
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()

        ir_default = self.env['ir.default'].sudo()

        ir_default.set(
            'product.template',
            "taxes_id",
            self.sale_tax_ids.ids,
            company_id=self.company_id.id)

        ir_default.set(
            'product.template',
            "supplier_taxes_id",
            self.purchase_tax_ids.ids,
            company_id=self.company_id.id)
