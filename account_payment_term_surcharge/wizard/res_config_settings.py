from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payment_term_surcharge_product_id = fields.Many2one(
        'product.product',
        related='company_id.payment_term_surcharge_product_id',
        string="Producto por defecto para los recargos", readonly=False
    )

    payment_term_surcharge_invoice_auto_post = fields.Boolean(
        related='company_id.payment_term_surcharge_invoice_auto_post',
        string= 'Validad automaticamente las facturas', readonly=False
    )
