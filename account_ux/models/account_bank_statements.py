##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    @api.multi
    def cancel_all_lines(self):
        for rec in self:
            rec.line_ids.filtered(
                'journal_entry_ids').button_cancel_reconciliation()
        return True
