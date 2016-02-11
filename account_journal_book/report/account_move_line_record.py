# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp.report import report_sxw
# from openerp import models
import time


# class general_ledger(report_sxw.rml_parse, common_report_header):
class JournalPrint(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(JournalPrint, self).__init__(cr, uid, name, context=context)
        self.localcontext['time'] = time
        self.localcontext['lang'] = context.get('lang')

    def set_context(self, objects, data, ids, report_type=None):
        if data['model'] == 'ir.ui.menu':
            form = data['form']
            journal_ids = form['journal_ids']

            domain = [('journal_id', 'in', journal_ids)]
            if form['fiscalyear_id']:
                domain.append(
                    ('period_id.fiscalyear_id', '=', form['fiscalyear_id']))

            if form['target_move'] == 'posted':
                domain.append(('state', '=', 'posted'))

            if form['filter'] == 'filter_period':
                period_ids = self.pool.get('account.period').build_ctx_periods(
                    self.cr, self.uid, form['period_from'], form['period_to'])
                domain.append(('period_id', 'in', period_ids))
            elif form['filter'] == 'filter_date':
                if form['date_from']:
                    domain.append(('date', '>=', form['date_from']))
                if form['date_to']:
                    domain.append(('date', '<', form['date_to']))
            move_ids = self.pool['account.move'].search(
                self.cr, self.uid, domain,
                order=form['sort_selection'] + ', id'
                )
        else:
            move_ids = []
            journalperiods = self.pool['account.journal.period'].browse(
                self.cr, self.uid, ids)
            for jp in journalperiods:
                move_ids = self.pool['account.move'].search(
                    self.cr, self.uid, [('period_id', '=', jp.period_id.id),
                                        ('journal_id', '=', jp.journal_id.id),
                                        ('state', '<>', 'draft')],
                    order='date,id')
        objects = self.pool['account.move'].browse(self.cr, self.uid, move_ids)
        super(JournalPrint, self).set_context(objects, data, ids, report_type)

# TODO migrar a nuevo formato
# class report_generalledger(models.AbstractModel):
#     _name = 'report.account.report_generalledger'
#     _inherit = 'report.abstract_report'
#     _template = 'account.report_generalledger'
#     _wrapped_report_class = JournalPrint

report_sxw.report_sxw(
    'report.account.journal.entries.report.wzd', 'account.journal.period',
    'account_journal_book/report/account_move_line_record.rml',
    parser=JournalPrint, header=False)
report_sxw.report_sxw(
    'report.account.journal.entries.report.wzd1', 'account.journal.period',
    'account_journal_book/report/account_move_line_record_h.rml',
    parser=JournalPrint, header=False)
