# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import api, fields, models
# from openerp.tools.translate import _


class AccountJournalBookReport(models.TransientModel):
    _inherit = "account.common.report"
    _name = "account.journal.book.report"
    _description = "Journal Book Report"

    # este campo ya existe en la clase oficial, lo recreamos
    # para cambiar la rel
    journal_ids = fields.Many2many(
        'account.journal',
        'account_journal_book_journal_rel',
        'acc_journal_entries_id',
        'journal_id',
        'Journals',
        required=True,
        ondelete='cascade',
    )
    next_entry_number = fields.Integer(
        string='Próximo número de asiento',
    )

    @api.multi
    def _print_report(self, data):
        data['form'].update(
            self.read(['sort_selection', 'landscape'])[0])
        # en realidad diario no lo mostramos y no dajamos que seleccione
        # domain = [('journal_id', 'in', self.journal_ids.ids)]

        # company_id esta invisible, lo ponemos por si no selecciona año
        # fiscal ni periodos, viene definido por el plan de cuentas
        domain = [('company_id', '=', self.company_id.id)]
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
        moves = self.env['account.move'].search(domain)
        # lines = self.env['account.move.line'].search(domain)
        # lines = self.env['account.book.line'].search(domain)
        # print 'domain', domain
        # print 'lines', lines
        # periods = lines.mapped('period_id').ids
        # print 'periods', periods

        return self.env['report'].with_context(
            period_ids=moves.mapped('period_id').ids,
            next_entry_number=self.next_entry_number,
            # period_ids=lines.mapped('period_id').ids,
            # periods=self.env['account.period'].browse(period_ids),
            # read=read,
            # number_in_books=number_in_books,
        ).get_action(
            moves, 'account_journal_book_report')
