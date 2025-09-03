from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    exchange_difference_product = fields.Many2one(
        "product.product",
        related="company_id.exchange_difference_product",
        readonly=False,
    )
