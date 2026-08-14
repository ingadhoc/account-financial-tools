from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """On posting an invoice, ``stock_account._post`` revalues the incoming/dropship
        moves (``stock.move._set_value``) against the invoiced price. The context flag makes
        the ``stock.move._set_value`` override skip that revaluation on moves migrated from
        v18, whose value is already booked. See task 70174.
        """
        return super(AccountMove, self.with_context(skip_migrated_stock_revaluation=True))._post(soft=soft)

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
