# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Nullable on purpose: NULL means "not frozen yet", the report falls back
    # to the dynamic computation via COALESCE. No default, no compute.
    historical_cost = fields.Monetary(
        currency_field="company_currency_id",
        store=True,
        readonly=True,
        copy=False,
        groups="base.group_user",
    )
    historical_cost_provisional = fields.Boolean(
        readonly=True,
        copy=False,
        groups="base.group_user",
    )

    def _freeze_historical_cost(self, anglo_saxon_price_ctx):
        self.ensure_one()
        # Signed as line.quantity, NOT flipped by move_type: that flip (core's
        # `-1 if move_type == 'out_refund'`) is for the COGS journal amount,
        # applied later by the report's _select(). _get_cogs_value() already
        # returns an abs() unit price (stock_account), so quantity carries the
        # only sign here — including the negative-quantity-line-inside-an-
        # out_invoice edge case (AC17).
        if self.product_id.is_storable:
            valuation_moves = self._get_historical_cost_moves()
            if valuation_moves:
                # Reads stock.move.value directly: _get_cogs_value() nets a
                # return's qty to zero and falls back to standard_price.
                self._complete_historical_cost_from_moves(valuation_moves)
            else:
                cogs_qty = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
                # Mirrors stock_account's own call (account_move.py,
                # _stock_account_prepare_realtime_out_lines_vals): replaces the
                # context on purpose, doesn't merge it.
                price_unit = self.with_context(anglo_saxon_price_ctx)._get_cogs_value()  # pylint: disable=context-overridden
                self.historical_cost = cogs_qty * price_unit
                self.historical_cost_provisional = True
        else:
            self.historical_cost = self.quantity * self.product_id.standard_price
            self.historical_cost_provisional = True

    def _get_historical_cost_moves(self):
        self.ensure_one()
        moves = self._get_stock_moves().filtered(lambda m: m.state == "done")
        if self.move_id.move_type == "out_refund":
            return_moves = moves.filtered(lambda m: m.is_in and m.origin_returned_move_id)
            return return_moves or moves.filtered(lambda m: not m.is_in)
        return moves.filtered(lambda m: not m.is_in)

    def _clear_historical_cost(self):
        # Writing False through the ORM on a Monetary field stores 0.0, not
        # SQL NULL — and 0.0 is a legitimate frozen value (a free sample),
        # distinct from "not frozen" (§1 of the spec). Direct SQL is the only
        # way to actually clear it back to NULL.
        if not self:
            return
        self.env.cr.execute(
            "UPDATE account_move_line SET historical_cost = NULL, historical_cost_provisional = NULL WHERE id IN %s",
            [tuple(self.ids)],
        )
        self.invalidate_recordset(["historical_cost", "historical_cost_provisional"])

    def _complete_historical_cost_from_moves(self, moves):
        self.ensure_one()
        total_qty = sum(
            moves.mapped(lambda move: move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id))
        )
        if not total_qty:
            return
        unit_value = sum(moves.mapped("value")) / total_qty
        cogs_qty = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
        self.historical_cost = cogs_qty * unit_value
        self.historical_cost_provisional = False
