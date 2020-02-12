##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    inverse_rate = fields.Float(
        digits=0,
        compute='_compute_inverse_rate',
        inverse='_inverse_inverse_rate',
        help='The rate of the currency from the currency of rate 1',
    )

    @api.depends('rate')
    def _compute_inverse_rate(self):
        for rec in self:
            rec.inverse_rate = 1.0 / rec.rate if rec.rate else 0.0

    def _inverse_inverse_rate(self):
        for rec in self:
            rec.rate = 1.0 / rec.inverse_rate if rec.inverse_rate else 0.0
