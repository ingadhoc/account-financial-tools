##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.onchange('available_journal_ids')
    def _onchange_available_journal_ids(self):
        """ Fix the use case where a journal only suitable for one kind of operation (lets said inbound) is selected
        and then the user selects "outbound" type, the journals remains selected."""
        if not self.journal_id or self.journal_id not in self.available_journal_ids._origin:
            self.journal_id = self.available_journal_ids._origin[:1]
