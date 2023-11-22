from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # campo a ser extendido y mostrar un nombre detemrinado en las lineas de
    # pago de un payment group o donde se desee (por ej. con cheque, retención,
    # etc)
    payment_method_description = fields.Char(
        compute='_compute_payment_method_description',
        string='Payment Method Desc.',
    )

    def _compute_is_internal_transfer(self):
        super()._compute_is_internal_transfer()
        if self._context.get('is_internal_transfer_menu'):
            self.is_internal_transfer = True

    @api.depends('payment_method_id')
    def _compute_payment_method_description(self):
        for rec in self:
            rec.payment_method_description = rec.payment_method_id.display_name
