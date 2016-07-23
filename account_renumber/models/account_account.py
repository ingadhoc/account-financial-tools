# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import Warning


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.multi
    def _check_allow_code_change(self):
        if self.env.user.has_group('account.group_account_manager'):
            return True
        return super(AccountAccount, self)._check_allow_code_change()
