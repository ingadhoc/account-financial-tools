from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _compute_account_id(self):
        """Book the purchase invoice line of a move migrated from v18 to the counterpart
        of its valuation entry, instead of to the stock valuation account.

        Out of the box (``stock_account``) this compute overwrites the line account with
        ``accounts['stock_valuation']`` for ``real_time`` products, booking the asset
        increase in the invoice itself. For a move whose valuation was ALREADY booked in
        v18 (``stock_valuation_migrated``) that increases the asset twice: the stock is
        already valued. The counterpart of the migrated entry is used instead —the credit of
        that increase— which is the account the vendor bill has to settle. See task 70174.
        """
        super()._compute_account_id()
        for line in self:
            move = line.move_id
            if not move.is_purchase_document() or line.display_type == "cogs":
                continue
            if not line._eligible_for_stock_account() or line.product_id.valuation != "real_time":
                continue
            stock_moves = line._get_stock_moves()
            if not stock_moves or not all(m.stock_valuation_migrated for m in stock_moves):
                continue
            counterpart_account = stock_moves[:1]._get_migrated_valuation_counterpart_account()
            if counterpart_account:
                line.account_id = counterpart_account

    # -- Reversal of the closing entry on invoicing ------------------------------
    def _get_stock_order_line(self):
        """Sale or purchase line this invoice line bills, if any."""
        self.ensure_one()
        if "sale_line_ids" in self._fields and len(self.sale_line_ids) == 1:
            return self.sale_line_ids
        if "purchase_line_id" in self._fields and self.purchase_line_id:
            return self.purchase_line_id
        return None

    @api.model
    def _get_stock_order_line_of_move(self, stock_move):
        """Sale or purchase line a stock move delivers or receives, if any."""
        for field in ("sale_line_id", "purchase_line_id"):
            if field in stock_move._fields and stock_move[field]:
                return stock_move[field]
        return None

    @api.model
    def _get_stock_closing_reversal_lines(self, order_line):
        """Valuation lines of the closing reversals the invoices of ``order_line``
        generated that still stand: posted, and not reversed themselves. Their quantity
        is what was taken back from each closing for that line."""
        lines = self.sudo().search(
            [
                ("cogs_origin_id", "in", order_line.invoice_lines.ids),
                ("parent_state", "=", "posted"),
                ("move_id.reversed_entry_id", "!=", False),
            ]
        )
        return lines.filtered(
            lambda line: not line.move_id.reversal_move_ids.filtered(lambda entry: entry.state == "posted")
        )

    def _get_stock_closing_reversal_data(self):
        """``[(closing, quantity, balance)]``: what posting this invoice line reverses
        from each closing entry that booked its deliveries or receipts.

        The invoice bills a stretch of the order line, from what the other posted
        invoices (net of credit notes) already billed. From each closing it reverses the
        part of that stretch the closing booked, capped by what the closing booked and is
        not reversed yet. The cap keeps a closing from being reversed twice when a credit
        note cancels an invoice and another one bills the same quantity again.

        The amount is the value the closing booked the moves at, prorated by quantity.
        ``balance`` is signed for the valuation account: a delivery was booked as a
        decrease, so its reversal is a debit; a receipt, a credit.
        """
        self.ensure_one()
        order_line = self._get_stock_order_line()
        if not order_line:
            return []
        stretches_by_closing = self.env["stock.move"]._get_closing_stretches(order_line)
        if not stretches_by_closing:
            return []
        uom = order_line.product_uom_id
        invoiced_before = 0.0
        for line in order_line.invoice_lines:
            if line.move_id == self.move_id or line.parent_state != "posted" or line.display_type != "product":
                continue
            sign = -1 if line.move_id.move_type in ("out_refund", "in_refund") else 1
            invoiced_before += sign * line.product_uom_id._compute_quantity(line.quantity, uom, round=False)
        lower = invoiced_before
        upper = lower + self.product_uom_id._compute_quantity(self.quantity, uom, round=False)
        reversed_by_closing = {}
        for line in self._get_stock_closing_reversal_lines(order_line):
            closing = line.move_id.reversed_entry_id
            reversed_by_closing[closing] = reversed_by_closing.get(closing, 0.0) + line.quantity
        sign = 1 if order_line._name == "sale.order.line" else -1
        currency = self.company_id.currency_id
        result = []
        for closing, stretches in stretches_by_closing.items():
            overlap = sum(max(0.0, min(stop, upper) - max(start, lower)) for _move, start, stop in stretches)
            booked = sum(stop - start for _move, start, stop in stretches)
            quantity = min(overlap, booked - reversed_by_closing.get(closing, 0.0))
            if uom.compare(quantity, 0.0) <= 0:
                continue
            moves = self.env["stock.move"].union(*(move for move, _start, _stop in stretches))
            moved = sum(move.product_uom._compute_quantity(move.quantity, uom, round=False) for move in moves)
            if not moved:
                continue
            amount = currency.round(sum(moves.mapped("value")) * quantity / moved)
            if not currency.is_zero(amount):
                result.append((closing, quantity, sign * amount))
        return result
