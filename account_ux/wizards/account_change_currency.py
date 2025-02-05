##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models


class AccountChangeCurrency(models.TransientModel):
    _name = "account.change.currency"
    _description = "Change Currency"

    @api.model
    def get_move(self):
        move = self.env["account.move"].browse(self._context.get("active_id", False))
        return move

    currency_from_id = fields.Many2one(
        "res.currency", string="Currency From", related="move_id.currency_id", help="Currency from Invoice"
    )
    currency_to_id = fields.Many2one(
        "res.currency",
        string="Currency to",
        required=True,
        help="Select a currency to apply on the invoice",
    )
    conversion_date = fields.Float(
        "Conversion Rate", required=True, digits=0, help="Select a rate to apply on the invoice"
    )
    move_id = fields.Many2one("account.move", default=get_move)

    @api.onchange("currency_to_id")
    def onchange_currency(self):
        if not self.currency_to_id:
            self.conversion_date = False
        else:
            currency = self.currency_from_id.with_context()

            self.conversion_date = self.env["res.currency"]._get_conversion_rate(
                from_currency=currency,
                to_currency=self.currency_to_id,
                company=self.move_id.company_id,
                date=self.move_id._get_invoice_currency_rate_date(),
            )

    def change_currency(self):
        self.ensure_one()
        message = _("Currency changed from %s to %s with rate %s") % (
            self.move_id.currency_id.name,
            self.currency_to_id.name,
            self.conversion_date,
        )

        move = self.move_id.with_context(check_move_validity=False)
        move.currency_id = self.currency_to_id.id
        for line in move.line_ids:
            # do not round on currency digits, it is rounded automatically
            # on price_unit precision
            if line.exists():
                line.price_unit = line.price_unit * self.conversion_date

        self.move_id.message_post(body=message)
        return {"type": "ir.actions.act_window_close"}
