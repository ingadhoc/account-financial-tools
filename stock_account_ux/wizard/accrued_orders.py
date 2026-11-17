from collections import defaultdict

from odoo import fields, models


class AccountAccruedOrdersWizard(models.TransientModel):
    _inherit = "account.accrued.orders.wizard"

    def _compute_move_vals(self):
        move_vals, orders, order_lines = super()._compute_move_vals()
        self._set_product_on_stock_accrual_lines(move_vals, order_lines)
        return move_vals, orders, order_lines

    def _set_product_on_stock_accrual_lines(self, move_vals, order_lines):
        """Name the product on the stock lines of the accrual, as the closing does on its
        valuation lines. The standard builds one stock line per order line with no
        product; the counterpart stays grouped by account.

        ``_get_accrual_pending_cogs_vals`` is overridden by purchase and sale, which this
        module does not depend on, so it is not extended: it is called again per order
        line and its stock lines are matched back to the entry by their values.
        """
        accrual_entry_date = self.env.context.get("accrual_entry_date")
        accrual_entry_date = fields.Date.from_string(accrual_entry_date) if accrual_entry_date else self.date
        product_ids_by_vals = defaultdict(list)
        for order_line in order_lines:
            vals_list, __ = self._get_accrual_pending_cogs_vals(order_line, accrual_entry_date)
            for vals in vals_list:
                product_ids_by_vals[self._get_accrual_vals_key(vals)].append(order_line.product_id.id)
        if not product_ids_by_vals:
            return
        for command in move_vals["line_ids"]:
            vals = command[2]
            product_ids = product_ids_by_vals.get(self._get_accrual_vals_key(vals))
            if product_ids and not vals.get("product_id"):
                vals["product_id"] = product_ids.pop(0)

    def _get_accrual_vals_key(self, vals):
        return tuple(sorted((key, repr(value)) for key, value in vals.items()))
