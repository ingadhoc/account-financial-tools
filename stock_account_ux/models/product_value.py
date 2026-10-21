from odoo import fields, models
from odoo.exceptions import UserError


class ProductValue(models.Model):
    _inherit = "product.value"

    def _get_booking_value(self):
        """Value this adjustment added to the inventory: what booking it on its own
        posts.

        ``adjustment`` is already a total, for a move and for a price change alike. The value
        of an outgoing move is negative, so its adjustment already has the direction of the
        inventory: an outgoing move worth more (more negative) takes more out. An internal
        move does not change it.
        """
        self.ensure_one()
        if self.move_id:
            if self.move_id.is_in or self.move_id.is_out:
                return self.adjustment
            return 0.0
        return self.currency_id.round(self.adjustment)

    def _get_valuation_product(self):
        self.ensure_one()
        return self.product_id or self.move_id.product_id

    def _get_valuation_labels(self):
        """Labels to name adjustments in user messages: the model has no name field."""
        return [f"{pv._get_valuation_product().display_name} ({fields.Date.to_string(pv.date.date())})" for pv in self]

    def action_value_product_values(self):
        """Open the manual valuation wizard to book the selected adjustments only."""
        # The wizard books in the current company, with its journal and accounts.
        if self.company_id != self.env.company:
            raise UserError(self.env._("Select value adjustments of the current company only."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Book Value Adjustments"),
            "res_model": "stock.move.valuation",
            "view_mode": "form",
            "target": "new",
            "context": {**self.env.context, "default_product_value_ids": self.ids},
        }
