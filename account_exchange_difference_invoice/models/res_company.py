from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    exchange_difference_product = fields.Many2one("product.product")
