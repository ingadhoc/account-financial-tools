from odoo import api, fields, models


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
        # Delegamos en el search method de stock.move recorriendo move_id.
        return [("move_id.related_account_move_id", operator, value)]
