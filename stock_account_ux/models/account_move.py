from datetime import datetime

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    allow_move_with_valuation_cancelation = fields.Boolean(compute="_compute_allow_move_with_valuation_cancelation")

    def _compute_allow_move_with_valuation_cancelation(self):
        with_valuation = self.filtered(
            lambda m: m.line_ids._get_stock_moves().filtered(
                lambda sm: sm.is_valued and sm._get_value(at_date=datetime.min) != sm._get_value()
            )
        )
        (self - with_valuation).allow_move_with_valuation_cancelation = False
        for rec in with_valuation:
            rec._compute_show_reset_to_draft_button()
            rec.allow_move_with_valuation_cancelation = rec.show_reset_to_draft_button
            rec.show_reset_to_draft_button = False
