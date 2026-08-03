# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Nullable on purpose: NULL means "not frozen yet", the report falls back
    # to the dynamic computation via COALESCE. No default, no compute.
    historical_cost = fields.Monetary(
        currency_field="company_currency_id",
        readonly=True,
        copy=False,
        groups="base.group_user",
    )
    historical_cost_provisional = fields.Boolean(
        readonly=True,
        copy=False,
        groups="base.group_user",
    )

    def _get_frozen_historical_cost_vals(self, anglo_saxon_price_ctx):
        """Values to freeze on this line; the caller writes them grouped."""
        self.ensure_one()
        # Signed as line.quantity, NOT flipped by move_type: that flip (core's
        # `-1 if move_type == 'out_refund'`) is for the COGS journal amount,
        # applied later by the report's _select(). _get_cogs_value() already
        # returns an abs() unit price (stock_account), so quantity carries the
        # only sign here — including the negative-quantity-line-inside-an-
        # out_invoice edge case (AC17).
        if not self.product_id.is_storable:
            return {
                "historical_cost": self.quantity * self.product_id.standard_price,
                "historical_cost_provisional": True,
            }
        valuation_moves = self._get_historical_cost_moves()
        if valuation_moves:
            # Reads stock.move.value directly: _get_cogs_value() nets a
            # return's qty to zero and falls back to standard_price.
            return self._get_historical_cost_vals_from_moves(valuation_moves)
        cogs_qty = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
        # Mirrors stock_account's own call (account_move.py,
        # _stock_account_prepare_realtime_out_lines_vals): replaces the
        # context on purpose, doesn't merge it.
        price_unit = self.with_context(anglo_saxon_price_ctx)._get_cogs_value()  # pylint: disable=context-overridden
        return {
            "historical_cost": cogs_qty * price_unit,
            "historical_cost_provisional": True,
        }

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
        # Flush first: a value still pending in the ORM cache would be written
        # after this UPDATE and bring the old value back.
        self.flush_recordset(["historical_cost", "historical_cost_provisional"])
        self.env.cr.execute(
            "UPDATE account_move_line SET historical_cost = NULL, historical_cost_provisional = NULL WHERE id IN %s",
            [tuple(self.ids)],
        )
        self.invalidate_recordset(["historical_cost", "historical_cost_provisional"])

    def _complete_historical_cost_from_moves(self, moves):
        vals = self._get_historical_cost_vals_from_moves(moves)
        if vals:
            self._write_historical_cost(vals)

    def _write_historical_cost(self, vals):
        # Direct SQL, like _clear_historical_cost: both fields are plain
        # columns with nothing computed on top of them, and going through
        # write() makes every line cascade into the account.move.line
        # recomputes, which is what dominates the cost of freezing.
        if not self:
            return
        self.flush_recordset(["historical_cost", "historical_cost_provisional"])
        self.env.cr.execute(
            "UPDATE account_move_line SET historical_cost = %s, historical_cost_provisional = %s WHERE id IN %s",
            [vals["historical_cost"], vals["historical_cost_provisional"], tuple(self.ids)],
        )
        self.invalidate_recordset(["historical_cost", "historical_cost_provisional"])

    def _get_historical_cost_vals_from_moves(self, moves):
        self.ensure_one()
        total_qty = sum(
            moves.mapped(lambda move: move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id))
        )
        if not total_qty:
            return {}
        cogs_qty = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
        branch_company = self._get_historical_cost_branch_company()
        if branch_company:
            # The parent company holds the valuation, and its cost is resolved
            # in stock.move._get_cogs_price_unit() (overridden by
            # stock_account_multicompany_ux). Reading `value` here would freeze
            # the branch cost and diverge from the COGS the core posts.
            unit_value = moves.with_context(branch_company=branch_company.id)._get_cogs_price_unit(cogs_qty)
        else:
            unit_value = sum(moves.mapped("value")) / total_qty
        return {
            "historical_cost": cogs_qty * unit_value,
            "historical_cost_provisional": False,
        }

    def _get_historical_cost_branch_company(self):
        """Invoice company when it is a branch selling a product whose valuation
        lives in its parent; empty recordset otherwise."""
        self.ensure_one()
        company = self.move_id.company_id
        parent_company = company.parent_id
        no_company = self.env["res.company"]
        if not parent_company or "shared_to_branches" not in self.env["product.category"]._fields:
            return no_company
        if not self.product_id.categ_id.with_company(parent_company).shared_to_branches:
            return no_company
        return company
