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

    def _get_frozen_historical_cost_vals(self):
        """Values to freeze on this line; the caller writes them grouped."""
        self.ensure_one()
        # Signed as line.quantity, NOT flipped by move_type: that flip (core's
        # `-1 if move_type == 'out_refund'`) is for the COGS journal amount,
        # applied later by the report's _select_list(). _get_cogs_value() already
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
            # Values only these moves: _get_cogs_value() nets a return's qty to
            # zero and then returns a zero unit price.
            return self._get_historical_cost_vals_from_moves(valuation_moves)
        cogs_qty = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
        # Mirrors the core's own call (account/models/account_move.py,
        # _get_cogs_lines_vals).
        price_unit = self._get_cogs_value()
        return {
            "historical_cost": cogs_qty * price_unit,
            "historical_cost_provisional": True,
        }

    def _get_historical_cost_moves(self):
        self.ensure_one()
        moves = self.cogs_move_ids.filtered(lambda m: m.state == "done")
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
        total_qty = sum(moves.mapped(lambda move: move.uom_id._compute_quantity(move.quantity, move.product_id.uom_id)))
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
            # stock.move.value is signed (negative for outgoing moves).
            unit_value = moves._get_price_unit(include_consigned=True, product=self.product_id)
        return {
            "historical_cost": cogs_qty * unit_value,
            "historical_cost_provisional": False,
        }

    def _set_cogs(self):
        res = super()._set_cogs()
        self.sudo()._follow_cogs_historical_cost()
        return res

    def _follow_cogs_historical_cost(self):
        """When the core corrects a posted COGS entry, the frozen cost of its
        invoice line follows it. Lines never frozen keep the dynamic report."""
        invoice_lines = self.cogs_origin_id.filtered(
            lambda line: line.move_id.state == "posted" and line.move_id.is_sale_document(include_receipts=True)
        )
        if not invoice_lines:
            return
        # NULL means "not frozen", and the ORM reads it as 0.0.
        invoice_lines.flush_recordset(["historical_cost"])
        self.env.cr.execute(
            "SELECT id FROM account_move_line WHERE id IN %s AND historical_cost IS NOT NULL",
            [tuple(invoice_lines.ids)],
        )
        frozen_ids = {row[0] for row in self.env.cr.fetchall()}
        cogs_by_origin_account = {}
        for line in self:
            cogs_by_origin_account.setdefault((line.cogs_origin_id.id, line.account_id.id), line)
        for invoice_line in invoice_lines.filtered(lambda line: line.id in frozen_ids):
            move = invoice_line.move_id
            invoice_line = invoice_line.with_company(move.company_id)
            accounts = invoice_line.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=move.fiscal_position_id)
            cogs_line = cogs_by_origin_account.get((invoice_line.id, accounts["stock_valuation"].id))
            if not cogs_line:
                continue
            cogs_qty = invoice_line.product_uom_id._compute_quantity(
                invoice_line.quantity, invoice_line.product_id.uom_id
            )
            invoice_line._write_historical_cost(
                {"historical_cost": cogs_qty * cogs_line.price_unit, "historical_cost_provisional": False}
            )

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
