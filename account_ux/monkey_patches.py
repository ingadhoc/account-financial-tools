from . import models
from . import wizards
from odoo.addons.stock_account.models.account_move import AccountMove

def monkey_patches():
    
    original_method = AccountMove._compute_show_reset_to_draft_button
    
    # monkey patch
    def _compute_show_reset_to_draft_button(self):
        original_method(self)
        if self._context.get('bypass_valuation_cancelation'):
            for move in self:
                if move.sudo().line_ids.stock_valuation_layer_ids:
                    move.show_reset_to_draft_button = False
    
    AccountMove._compute_show_reset_to_draft_button = _compute_show_reset_to_draft_button
