# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves.filtered(lambda move: move.state == "done")._complete_provisional_historical_cost()
        return moves

    def _complete_provisional_historical_cost(self):
        # Reads stock.move.value directly, never _get_cogs_value(): calling
        # _get_cogs_value() here would make the line count itself, since
        # sale_stock's _get_posted_cogs_value() sums COGS lines of the whole
        # order without filtering state, and this invoice's own COGS line
        # already exists by the time delivery happens.
        # sudo(): _action_done runs as the inventory user, who has no read
        # access to account.move.line (account/security/ir.model.access.csv).
        candidate_lines = self._get_historical_cost_candidate_lines().filtered(
            lambda line: line.historical_cost_provisional and line.display_type == "product"
        )
        for line in candidate_lines:
            related_moves = self.filtered(lambda move: move.sale_line_id in line.sale_line_ids)
            if related_moves:
                line._complete_historical_cost_from_moves(related_moves)

    def _get_historical_cost_candidate_lines(self):
        # Inverse of account.move.line._get_stock_moves() (sale_stock's
        # sale_line_ids.move_ids), walked backwards on purpose: searching
        # account_move_line by product would scan the whole table, keep
        # never-delivered lines as candidates forever, and need one
        # _get_stock_moves() per candidate.
        if "sale_line_id" not in self._fields:
            return self.env["account.move.line"]
        return self.sudo().sale_line_id.invoice_lines
