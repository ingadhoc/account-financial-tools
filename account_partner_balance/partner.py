# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api, _


class res_partner(models.Model):
    _inherit = 'res.partner'

    balance = fields.Float(
        compute='_get_balance',
        string=_('Balance'),
        )

    @api.one
    @api.depends('debit', 'credit')
    def _get_balance(self):
        self.balance = self.credit - self.debit
