from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """On posting an invoice, ``stock_account._post`` revalues the incoming/dropship
        moves (``stock.move._set_value``) against the invoiced price. The context flag makes
        the ``stock.move._set_value`` override skip that revaluation on moves migrated from
        v18, whose value is already booked. See task 70174.
        """
        posted = super(AccountMove, self.with_context(skip_migrated_stock_revaluation=True))._post(soft=soft)
        posted.filtered(lambda move: move.move_type in ("out_invoice", "in_invoice"))._reverse_stock_closings()
        return posted

    def button_draft(self):
        self.filtered(lambda move: move.move_type in ("out_invoice", "in_invoice"))._cancel_stock_closing_reversals()
        return super().button_draft()

    def _reverse_stock_closings(self):
        """Reverse the part of the closing entries the invoice bills.

        For perpetual products the invoice books the cost (COGS on a customer invoice,
        the stock valuation account on a vendor bill). When a closing entry generated
        before it already booked those deliveries or receipts, the cost was booked twice.
        This separate entry takes back from each closing what the invoice bills, so the
        cost stays booked by the invoice alone.

        Plain journal entries tied with standard fields: ``reversed_entry_id`` is the
        closing, and ``cogs_origin_id`` on the valuation line is the invoice line that
        generated it, which is how the quantity already reversed is read back.
        """
        for invoice in self:
            data_by_closing = {}
            for line in invoice.invoice_line_ids.filtered(lambda line: line.display_type == "product"):
                product = line.product_id.with_company(invoice.company_id)
                if not product.is_storable or product.valuation != "real_time":
                    continue
                for closing, quantity, balance in line._get_stock_closing_reversal_data():
                    data_by_closing.setdefault(closing, []).append((line, quantity, balance))
            for closing, data in data_by_closing.items():
                self.env["account.move"].sudo().create(
                    invoice._prepare_stock_closing_reversal_vals(closing, data)
                )._post(soft=False)

    def _prepare_stock_closing_reversal_vals(self, closing, data):
        """Dated on the invoice, or on the closing if the invoice is dated before it, so
        the reversal never lands before the entry it reverses."""
        self.ensure_one()
        company = self.company_id
        label = self.env._("Closing reversal: %(invoice)s", invoice=self.name)
        line_vals = []
        for line, quantity, balance in data:
            product = line.product_id.with_company(company)
            valuation_account = product._get_product_accounts()["stock_valuation"]
            variation_account = valuation_account.account_stock_variation_id or company.expense_account_id
            line_vals += [
                {
                    "name": f"{label} - {product.display_name}",
                    "account_id": valuation_account.id,
                    "product_id": product.id,
                    "quantity": quantity,
                    "product_uom_id": line._get_stock_order_line().product_uom_id.id,
                    "debit": balance if balance > 0 else 0.0,
                    "credit": -balance if balance < 0 else 0.0,
                    "cogs_origin_id": line.id,
                },
                {
                    "name": label,
                    "account_id": variation_account.id,
                    "product_id": product.id,
                    "debit": -balance if balance < 0 else 0.0,
                    "credit": balance if balance > 0 else 0.0,
                },
            ]
        return {
            "move_type": "entry",
            "journal_id": closing.journal_id.id,
            "company_id": company.id,
            "date": max(self.date, closing.date),
            "ref": label,
            "reversed_entry_id": closing.id,
            "line_ids": [(0, 0, vals) for vals in line_vals],
        }

    def _cancel_stock_closing_reversals(self):
        """Undo the closing reversals of invoices sent back to draft, so the closing books
        those deliveries again. Cancelled rather than deleted, which would leave a gap in
        the journal sequence; a locked one (hashed journal) is reversed instead."""
        reversals = (
            self.env["account.move.line"]
            .sudo()
            .search(
                [
                    ("cogs_origin_id", "in", self.invoice_line_ids.ids),
                    ("parent_state", "=", "posted"),
                    ("move_id.reversed_entry_id", "!=", False),
                ]
            )
            .move_id.filtered(lambda entry: not entry.reversal_move_ids.filtered(lambda rev: rev.state == "posted"))
        )
        if not reversals:
            return
        draftable = reversals.filtered("show_reset_to_draft_button")
        draftable.button_draft()
        draftable.button_cancel()
        (reversals - draftable)._reverse_moves(cancel=True)

    def _stock_account_prepare_realtime_out_lines_vals(self):
        """Avoid booking the expense twice when invoicing in v19 moves already valued in
        v18.

        Out of the box, posting the invoice generates the anglo-saxon COGS lines for every
        ``real_time`` product line (see ``stock_account``'s ``account.move._post``, which
        calls this method). That computation starts from the invoice lines and does NOT look
        at ``stock.move.account_move_id``, so it does not know the move delivered in v18
        already has its valuation entry, re-attached by the 18->19 post-migration. Without
        this filter the expense would be recognised twice: once in v18 and once in the v19
        invoice COGS.

        Only the lines whose stock moves are ALL flagged ``stock_valuation_migrated`` are
        pruned; regular v19 deliveries keep generating their COGS as usual.
        """
        vals_list = super()._stock_account_prepare_realtime_out_lines_vals()
        if not vals_list:
            return vals_list
        skip_line_ids = set()
        for move in self:
            for line in move.invoice_line_ids:
                stock_moves = line._get_stock_moves()
                if stock_moves and all(m.stock_valuation_migrated for m in stock_moves):
                    skip_line_ids.add(line.id)
        if not skip_line_ids:
            return vals_list
        return [vals for vals in vals_list if vals.get("cogs_origin_id") not in skip_line_ids]
