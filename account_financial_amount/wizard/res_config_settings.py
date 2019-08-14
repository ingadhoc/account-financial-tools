##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_account_use_financial_amounts = fields.Boolean(
        "Use Financial Amounts",
        help='Display Financial amounts on partner debts views and reports.\n'
        'Financial amounts are amounts on other currency converted to company '
        'currency on todays exchange.',
        implied_group='account_financial_amount.account_use_financial_amounts')
