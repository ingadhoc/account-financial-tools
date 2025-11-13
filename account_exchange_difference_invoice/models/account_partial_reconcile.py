from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def unlink(self):
        """Borramos asientos de diferencia de cambio al desconciliar pagos para evitar tener demasiados asientos.
        Solo lo hacemos si el asiento no fue factura.
        Solo lo hacemos si tienen este feature activo en la compañía (campo exchange_difference_product definido)"""
        exchange_move = False
        if (
            self.exchange_move_id
            and self.company_id.exchange_difference_product
            and not self.exchange_move_id.exchange_reversal_id
        ):
            exchange_move = self.exchange_move_id
            self.exchange_move_id = False
        res = super().unlink()
        if exchange_move:
            exchange_move.button_draft()
            exchange_move.unlink()
        return res
