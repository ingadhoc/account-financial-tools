# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, fields
# from openerp.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.one
    @api.onchange('bank_id', 'bank_acc_number')
    def set_name_from_bank_account(self):
        # we only use this onchange if we are on banks menu
        # if 'default_type' in self._context:
        if self._context.get('set_bank_name'):
            name = self.bank_acc_number
            if name and self.bank_id:
                name = self.bank_id.name + ': ' + name
            self.name = name

    debit_card_days_for_collection = fields.Integer(
        help='This number of days will be added to the date of inbound debit '
        'card payments to get the due date, usefull for cashflow analysis'
    )
    credit_card_days_for_collection = fields.Integer(
        help='This number of days will be added to the date of inbound credit '
        'card payments to get the due date, usefull for cashflow analysis'
    )
    acquirer_ids = fields.One2many(
        'payment.acquirer',
        'journal_id',
        'Acquirers',
        help='Acquirer that use this journal to register online payments '
        'journal entries',
    )
