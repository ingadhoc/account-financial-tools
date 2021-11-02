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

    def button_cancel_reconciliation(self):
        """ Clean move_name to allow reconciling with new line.
        """
        res = super().button_cancel_reconciliation()
        self.write({'move_name': False})
        return res

    # TODO remove in version 15.0 only needed to clean up some statements with move name is set and it should not in
    # order to be able to reconcile the line statement line in future
    def button_fix_clean_move_name(self):
        self.write({'move_name': False})
