# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.one
    @api.onchange('bank_id', 'bank_acc_number')
    def set_name_from_bank_account(self):
        # we only use this onchange if we are on banks menu
        if 'default_type' in self._context:
            name = self.bank_acc_number
            if name and self.bank_id:
                name = self.bank_id.name + ': ' + name
            self.name = name
