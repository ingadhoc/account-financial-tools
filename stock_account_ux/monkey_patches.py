from . import models
from odoo.addons.stock_account.models.account_move import AccountMove

def monkey_patches():

    # monkey patch
    def _compute_show_reset_to_draft_button(self):
        # Bypasseamos el método _compute_show_reset_to_draft_button de stock account para que vaya al super del padre 
        super(AccountMove,self)._compute_show_reset_to_draft_button()

    AccountMove._compute_show_reset_to_draft_button = _compute_show_reset_to_draft_button
