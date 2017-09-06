# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    inverse_rate = fields.Float(
        'Current Inverse Rate', digits=(12, 4),
        compute='_compute_inverse_rate',
        help='The rate of the currency from the currency of rate 1 (0 if no '
                'rate defined).'
    )

    @api.multi
    @api.depends('rate')
    def _compute_inverse_rate(self):
        for rec in self:
            rec.inverse_rate = rec.rate and (
                1.0 / (rec.rate))


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    inverse_rate = fields.Float(
        'Inverse Rate', digits=(12, 4),
        compute='_compute_inverse_rate',
        inverse='_inverse_inverse_rate',
        help='The rate of the currency from the currency of rate 1',
    )

    @api.multi
    @api.depends('rate')
    def _compute_inverse_rate(self):
        for rec in self:
            rec.inverse_rate = rec.rate and (1.0 / (rec.rate))

    @api.multi
    def _inverse_inverse_rate(self):
        for rec in self:
            rec.rate = rec.inverse_rate and (1.0 / (rec.inverse_rate))
