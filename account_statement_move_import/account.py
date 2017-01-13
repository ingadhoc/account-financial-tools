# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    exclude_on_statements = fields.Boolean(
        'Exclude on Statements',
        help='Exclude this move line suggestion on statements',
    )
