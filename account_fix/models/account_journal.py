# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class AccountJorunal(models.Model):

    _inherit = "account.journal"

    @api.multi
    def create_bank_statement(self):
        """
        overwrite this method o remove the write of bank_statements_source
        because user may not have rights to write and also this is not necesary
        """
        # self.bank_statements_source = 'manual'
        action = self.env.ref('account.action_bank_statement_tree').read()[0]
        action.update({
            'views': [[False, 'form']],
            'context': "{'default_journal_id': " + str(self.id) + "}",
        })
        return action
