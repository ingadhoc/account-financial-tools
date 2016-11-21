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

    @api.multi
    def _print_report(self, data):
        data['form'].update(
            self.read(['sort_selection', 'landscape'])[0])
        if self.landscape:
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
