# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models


class ir_configparameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.one
    @api.constrains('key', 'value')
    def update_debt_detail(self):
        # we make this to avoid require updating module when changing this
        # parameter
        if self.key == 'account_debt_management.date_maturity_type':
            self.env['account.debt.line'].init()
