from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def _modify_default_reverse_values(self, origin_move):
        res = super()._modify_default_reverse_values(origin_move)
        res["invoice_user_id"] = origin_move.invoice_user_id.id
        return res
