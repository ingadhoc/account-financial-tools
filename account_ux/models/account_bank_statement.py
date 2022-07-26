##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, models
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def button_edit(self):
        if any(statement.state != 'posted' for statement in self):
            raise UserError(_("Only posted statements can be edited."))
        self.write({'state': 'open'})
