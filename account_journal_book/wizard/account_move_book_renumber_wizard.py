# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class account_move_book_renumber(models.TransientModel):
    _name = "account.move.book.move.renumber"
    _description = "Account Move Book renumber wizard"

    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        default=lambda self: self.env.user.company_id
    )
    numbering_order = fields.Selection([
        ('by_date_per_period', 'By Date per Period'),
        ('by_date', 'By Date'),
    ],
        'Numbering Order',
        required=True,
        default='by_date_per_period'
    )
    sequence_id = fields.Many2one(
        'ir.sequence',
        'Book Number Sequence',
        domain="[('code', '=', 'journal.book.sequence'), "
        "'|', ('company_id', '=', company_id), ('company_id', '=', False)],",
        context={'default_code': 'journal.book.sequence'},
        help='If no sequence provided then it wont be numbered',
        required=True,
    )
    journal_ids = fields.Many2many(
        'account.journal',
        'account_journal_book_renumber_rel',
        'wizard_id', 'journal_id',
        required=True,
        domain="[('company_id', '=', company_id)]",
        help="Journals to renumber",
        string="Journals"
    )
    period_ids = fields.Many2many(
        'account.period',
        'account_period_book_renumber_rel',
        'wizard_id', 'period_id',
        required=True,
        help='Fiscal periods to renumber',
        domain="[('company_id', '=', company_id), ('state', '=', 'draft')]",
        string="Periods",
        ondelete='null'
    )
    number_next = fields.Integer(
        related='sequence_id.number_next_actual',
        readonly=True,
        # 'First Number',
        # required=True,
        # default=1,
        # help="Journal sequences will start counting on this number"
    )
    state = fields.Selection([
        ('init', 'Initial'),
        ('renumber', 'Renumbering')],
        readonly=True,
        default='init',
    )
    grouped_journal_ids = fields.Many2many(
        'account.journal',
        string='Grouped Journals',
        domain="[('company_id', '=', company_id)]",
        help='Group Entries of this journals and number with same number',
    )

    @api.onchange('journal_ids')
    def onchange_journals(self):
        self.grouped_journal_ids = self.grouped_journal_ids.search([
            ('id', '=', self.journal_ids.ids),
            ('type', 'in', ['sale', 'purchase']),
        ])

    @api.onchange('company_id')
    def onchange_company(self):
        self.journal_ids = self.journal_ids.search(
            [('company_id', '=', self.company_id.id)])
        self.period_ids = self.period_ids.search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'draft'),
        ])

        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'journal.book.sequence'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not sequence:
            sequence = sequence.search([
                ('code', '=', 'journal.book.sequence'),
                ('company_id', '=', False)
            ], limit=1)
        self.sequence_id = sequence

    # @api.onchange('sequence_id')
    # def onchange_sequence(self):
    #     self.next_number = self.sequence_id.number_next_actual

    @api.multi
    def renumber(self):
        """
        Action that renumbers all the posted moves on the given
        journal and periods, and returns their ids.
        """
        self.ensure_one()
        _logger.debug("Searching for account moves to renumber.")
        # TODO ver si queremos ordenr por periodo o a todos los movimientos
        # juntos
        moves = self.env['account.move'].search([
            ('journal_id', 'in', self.journal_ids.ids),
            ('period_id', '=', self.period_ids.ids),
            ('state', '=', 'posted')],
            order='date,id')
        if self.numbering_order == 'by_date':
            moves.moves_renumber(self.sequence_id, self.grouped_journal_ids)
        else:
            for period in self.period_ids:
                self.env['account.move'].search([
                    ('journal_id', 'in', self.journal_ids.ids),
                    ('period_id', '=', period.id),
                    ('state', '=', 'posted')],
                    order='date,id').moves_renumber(
                        self.sequence_id, self.grouped_journal_ids)

        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account.view_move_tree')
        context = self._context.copy()
        context['search_default_show_number_in_book'] = 1
        res = {
            'type': 'ir.actions.act_window',
            'name': _("Renumbered account moves"),
            'res_model': 'account.move',
            'domain': ("[('id', 'in', %s)]" % (moves.ids)),
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id,
            'context': context,
            'target': 'current',
        }
        return res
