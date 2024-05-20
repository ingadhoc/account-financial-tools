from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    allow_move_with_valuation_cancelation = fields.Boolean(compute='_compute_allow_move_with_valuation_cancelation')

    def _compute_allow_move_with_valuation_cancelation(self):
        with_valuation = self.sudo().filtered('line_ids.stock_valuation_layer_ids')
        (self - with_valuation).allow_move_with_valuation_cancelation = False
        for rec in with_valuation:
            rec.allow_move_with_valuation_cancelation = not rec.show_reset_to_draft_button
            if rec.restrict_mode_hash_table:
                rec.with_context(bypass_valuation_cancelation= True)._compute_show_reset_to_draft_button()
                rec.allow_move_with_valuation_cancelation = rec.show_reset_to_draft_button
