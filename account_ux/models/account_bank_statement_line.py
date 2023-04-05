##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    duplicated_group = fields.Char(
        readonly=True,
        help='Technical field used to store information group a possible duplicates bank statement line')
