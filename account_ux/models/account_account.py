##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    analytic_distribution_required = fields.Boolean(
        string='Analytic Distribution Required?',
        help="If True, then an analytic distribution will be required when posting "
        "journal entries with this account.",
    )
