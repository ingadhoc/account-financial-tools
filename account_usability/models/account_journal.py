# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, fields
# from openerp.exceptions import UserError
from openerp.tools.misc import formatLang


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

    @api.multi
    def get_journal_dashboard_datas(self):
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        if self.type in ['sale', 'purchase']:
            currency = self.currency_id or self.company_id.currency_id
            sum_waiting = 0
            query = """SELECT state, residual_signed, currency_id AS currency
                       FROM account_invoice
                       WHERE journal_id = %s
                       AND state NOT IN ('paid', 'cancel');"""
            self.env.cr.execute(query, (self.id,))
            query_results = self.env.cr.dictfetchall()
            for result in query_results:
                cur = self.env['res.currency'].browse(result.get('currency'))
                if result.get('state') == 'open':
                    sum_waiting += cur.compute(
                        result.get('residual_signed'), currency)
            res.update({'sum_waiting': formatLang(
                self.env, sum_waiting or 0.0,
                currency_obj=self.currency_id or self.company_id.currency_id)})
        return res
