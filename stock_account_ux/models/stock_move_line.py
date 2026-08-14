from odoo import api, fields, models
from odoo.exceptions import UserError

# Context key with the moves only partly selected (some of their lines), to warn about
# it in the valuation wizard.
PARTIAL_LINES_CTX = "stock_valuation_partial_line_moves"


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    related_account_move_id = fields.Many2one(
        comodel_name="account.move",
        compute="_compute_related_account_move_id",
        search="_search_related_account_move_id",
        string="Journal Entry",
    )

    @api.depends("move_id.related_account_move_id")
    def _compute_related_account_move_id(self):
        for line in self:
            line.related_account_move_id = line.move_id.related_account_move_id

    def _search_related_account_move_id(self, operator, value):
        # Delegate to stock.move's search method by walking move_id.
        return [("move_id.related_account_move_id", operator, value)]

    def action_value_moves(self):
        """Value from Moves History, which lists ``stock.move.line``.

        The unit of valuation is the MOVE, not the line: the moves of the selected lines are
        resolved (deduplicated) and the ``stock.move`` action takes over. A move with only
        some of its lines selected is still valued whole, which the wizard warns about so it
        does not come as a surprise.
        """
        moves = self.move_id.filtered(lambda m: m.state == "done")
        if not moves:
            raise UserError(self.env._("Only done moves can be valued."))
        action = moves.action_value_moves()
        partially_selected = moves.filtered(lambda m: m.move_line_ids - self)
        if partially_selected:
            action["context"][PARTIAL_LINES_CTX] = partially_selected.ids
        return action
