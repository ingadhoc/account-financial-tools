##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    exclude_on_statements = fields.Boolean(
        'Exclude on Statements',
        help='Exclude this move line suggestion on statements',
    )
