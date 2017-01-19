# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class account_move(models.Model):
    _inherit = 'account.move'

    number_in_book = fields.Char(
        string='Number in Book',
        help='This number is set when closing a period or by running a wizard'
    )

    # @api.model
    # def get_book_line_value(self, number_in_book, field):
    #     recs = self.search([('number_in_book', '=', number_in_book)])
    #     if field in ['debit', 'credit']:
    #         print "'line_id.' + field", 'line_id.' + field
    #         return sum(recs.mapped('line_id.' + field))
    #     elif field in ['date']:
    #         return min(recs.mapped(field))

    #     if len(recs) > 1:
    #         return 'aaa'
    #     else:
    #         return recs[field]

    # we dont want it as we allow to group moves
    # _sql_constraints = [
    #     ('number_in_book_uniq', 'unique(number_in_book, journal_id)',
    #         'Number in Book must be unique per Journal!')]

    @api.multi
    def moves_renumber(self, sequence, grouped_journals=None):
        """
        We use sql instead of write to avoid constraints
        """
        if grouped_journals:
            for journal in grouped_journals:
                journal_moves = self.filtered(
                    lambda x: x.journal_id == journal)
                if not journal_moves:
                    continue
                fiscalyear = journal_moves[0].period_id.fiscalyear_id
                number = sequence.with_context(
                    fiscalyear_id=fiscalyear.id)._next()
                self._cr.execute("""
                    UPDATE account_move
                    SET number_in_book=%s
                    WHERE id in %s""", (number, tuple(journal_moves.ids),))
                self -= journal_moves
        _logger.info("Renumbering %d account moves.", len(self.ids))
        for move in self:
            number = sequence.with_context(
                fiscalyear_id=move.period_id.fiscalyear_id.id)._next()
            print 'a2', number
            self._cr.execute("""
                UPDATE account_move
                SET number_in_book=%s
                WHERE id in %s""", (number, tuple(move.ids),))
            # new_number = sequence.with_context(
            #     fiscalyear_id=move.period_id.fiscalyear_id.id)._next()
            # move.number_in_book = new_number
