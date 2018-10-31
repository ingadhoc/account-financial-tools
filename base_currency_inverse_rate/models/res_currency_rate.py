##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    inverse_rate = fields.Float(
        'Inverse Rate', digits=(12, 4),
        compute='_compute_inverse_rate',
        inverse='_inverse_inverse_rate',
        help='The rate of the currency from the currency of rate 1',
    )
    rate = fields.Float(digits=(7, 9))

    @api.multi
    @api.depends('rate')
    def _compute_inverse_rate(self):
        for rec in self:
            rec.inverse_rate = rec.rate and (1.0 / (rec.rate))

    @api.multi
    def _inverse_inverse_rate(self):
        for rec in self:
            rec.rate = rec.inverse_rate and (1.0 / (rec.inverse_rate))
