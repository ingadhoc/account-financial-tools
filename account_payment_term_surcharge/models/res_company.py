from odoo import api, exceptions, fields, models, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    payment_term_surcharge_product_id = fields.Many2one(
        'product.product',
        'Surcharge Product',
    )

    payment_term_surcharge_invoice_auto_post = fields.Boolean()
