##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def button_cancel_reconciliation(self):
        """ Clean move_name to allow reconciling with new line.
        """
        res = super().button_cancel_reconciliation()
        self.write({'move_name': False})
        return res
