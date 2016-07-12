# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models


class account_report_general_ledger(models.TransientModel):
    _inherit = "account.report.general.ledger"

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['landscape',  'initial_balance', 'amount_currency', 'sortby'])[0])
        # we comment this as we whant initial balance the same way
        # if not data['form']['fiscalyear_id']:# GTK client problem onchange does not consider in save record
            # data['form'].update({'initial_balance': False})

        if data['form']['landscape'] is False:
            data['form'].pop('landscape')
        else:
            context['landscape'] = data['form']['landscape']

        return self.pool['report'].get_action(cr, uid, [], 'account.report_generalledger', data=data, context=context)
