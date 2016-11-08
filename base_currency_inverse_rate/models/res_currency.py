# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class res_currency(models.Model):
    _inherit = "res.currency"

    inverse_rate = fields.Float(
        'Current Inverse Rate', digits=(12, 4),
        compute='get_inverse_rate',
        help='The rate of the currency from the currency of rate 1 (0 if no '
                'rate defined).'
    )

    @api.one
    @api.depends('rate')
    def get_inverse_rate(self):
        self.inverse_rate = self.rate and (
            1.0 / (self.rate))


class res_currency_rate(models.Model):
    _inherit = "res.currency.rate"

    inverse_rate = fields.Float(
        'Inverse Rate', digits=(12, 4),
        compute='get_inverse_rate',
        inverse='set_inverse_rate',
        help='The rate of the currency from the currency of rate 1',
    )

    @api.one
    @api.depends('rate')
    def get_inverse_rate(self):
        self.inverse_rate = self.rate and (1.0 / (self.rate))

    @api.one
    def set_inverse_rate(self):
        self.rate = self.inverse_rate and (1.0 / (self.inverse_rate))
