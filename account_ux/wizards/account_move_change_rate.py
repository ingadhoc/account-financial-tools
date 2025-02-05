##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.tools import float_round


class AccountMoveChangeRate(models.TransientModel):
    _name = "account.move.change.rate"
    _description = "account.move.change.rate"

    @api.model
    def get_move(self):
        move = self.env["account.move"].browse(self._context.get("active_id", False))
        return move

    currency_rate = fields.Float(required=True, digits=(16, 6), help="Select a rate to apply on the invoice")
    move_id = fields.Many2one("account.move", default=get_move)

    @api.onchange("move_id")
    def _onchange_move(self):
        self.currency_rate = self.move_id.inverse_invoice_currency_rate

    def confirm(self):
        message = _("Currency rate changed from '%s' to '%s' . Currency rate forced") % (
            float_round(self.move_id.inverse_invoice_currency_rate, 2),
            float_round(self.currency_rate, 2),
        )
        self.move_id.write({"invoice_currency_rate": 1 / self.currency_rate})
        self.move_id.message_post(body=message)
        return {"type": "ir.actions.act_window_close"}
