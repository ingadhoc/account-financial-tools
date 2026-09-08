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
        candidate_lines = self.env["account.move.line"].search(
            [
                ("historical_cost_provisional", "=", True),
                ("display_type", "=", "product"),
                ("product_id", "in", self.product_id.ids),
            ]
        )
        for line in candidate_lines:
            related_moves = (line._get_stock_moves() & self).filtered(lambda move: move.state == "done")
            if related_moves:
                line._complete_historical_cost_from_moves(related_moves)
