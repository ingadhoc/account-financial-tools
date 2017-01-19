# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import api, fields, models
# from openerp.tools.translate import _


class AccountJournalEntriesReport(models.TransientModel):
    _inherit = "account.common.report"
    _name = "account.journal.entries.report"
    _description = "Print journal by entries"

    journal_ids = fields.Many2many(
        'account.journal',
        'account_journal_entries_journal_rel',
        'acc_journal_entries_id',
        'journal_id',
        'Journals',
        required=True,
        ondelete='cascade',
    )
    sort_selection = fields.Selection(
        [('date', 'By date'),
         ('name', 'By entry number'),
         ('number_in_book', 'Number in Book'),
         ('ref', 'By reference number')],
        'Entries Sorted By',
        required=True,
        default='number_in_book',
    )
    landscape = fields.Boolean(
        'Landscape mode',
        default=True,
    )
    group_by_number_in_book = fields.Boolean(
        default=True,
    )

    @api.multi
    def _print_report(self, data):
        data['form'].update(
            self.read(['sort_selection', 'landscape'])[0])
        print 'data', data
        if self.group_by_number_in_book:
            return self.print_ods_report()
        elif self.landscape:
            report_name = 'account.journal.entries.report.wzd1'
        else:
            report_name = 'account.journal.entries.report.wzd'
        # TODO deberia andar asi pero por ser rml no esta funcionando
        # return self.env['report'].get_action(self, report_name, data=data)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': self._context,
        }

    @api.multi
    def print_ods_report(self):

        domain = [('journal_id', 'in', self.journal_ids.ids)]
        if self.fiscalyear_id:
            domain.append(
                ('period_id.fiscalyear_id', '=', self.fiscalyear_id.id))
        if self.target_move == 'posted':
            domain.append(('state', '=', 'posted'))

        if self.filter == 'filter_period':
            period_ids = self.env['account.period'].build_ctx_periods(
                self.period_from.id, self.period_to.id)
            domain.append(('period_id', 'in', period_ids))
        elif self.filter == 'filter_date':
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<', self.date_to))
        lines = self.env['account.book.line'].search(domain)
        return self.env['report'].with_context(
            # read=read,
            # number_in_books=number_in_books,
        ).get_action(
            lines, 'account_book_report')

        # domain = [('journal_id', 'in', self.journal_ids.ids)]
        # if self.fiscalyear_id:
        #     domain.append(
        #         ('period_id.fiscalyear_id', '=', self.fiscalyear_id.id))
        # if self.target_move == 'posted':
        #     domain.append(('state', '=', 'posted'))

        # if self.filter == 'filter_period':
        #     period_ids = self.env['account.period'].build_ctx_periods(
        #         self.period_from.id, self.period_to.id)
        #     domain.append(('period_id', 'in', period_ids))
        # elif self.filter == 'filter_date':
        #     if self.date_from:
        #         domain.append(('date', '>=', self.date_from))
        #     if self.date_to:
        #         domain.append(('date', '<', self.date_to))
        # read = self.env['account.move'].read_group(
        #     domain, ['number_in_book'], ['number_in_book'])
        # number_in_books = [x['number_in_book'] for x in read]
        # return self.env['report'].with_context(
        #     number_in_books=number_in_books,
        # ).get_action(
        #     self.env['account.move'], 'account_book_report')
