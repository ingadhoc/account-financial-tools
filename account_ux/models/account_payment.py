from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _compute_is_internal_transfer(self):
        super()._compute_is_internal_transfer()
        if self._context.get('is_internal_transfer_menu'):
            self.is_internal_transfer = True
