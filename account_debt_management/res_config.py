# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models


class argentinian_base_configuration(models.TransientModel):
    _inherit = 'account.config.settings'

    group_account_use_financial_amounts = fields.Boolean(
        "Use Financial Amounts",
        help='Display Financial amounts on partner debts views and reports.\n'
        'Financial amounts are amounts on other currency converted to company '
        'currency on todays exchange.',
        implied_group='account_debt_management.account_use_financial_amounts')
