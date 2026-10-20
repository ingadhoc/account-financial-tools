# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        # Must run before super(), which is where account creates the COGS
        # lines (_create_cogs_lines), so the frozen value is the same one the
        # core uses to build them.
        self._freeze_historical_cost()
        return super()._post(soft)

    def _freeze_historical_cost(self):
        lines_by_vals = defaultdict(lambda: self.env["account.move.line"])
        for move in self:
            if not move.is_sale_document(include_receipts=True):
                continue
            # Deliberately NOT excluded for move_reverse_cancel (unlike
            # stock_account._post): the cancellation credit note also needs
            # its cost frozen, otherwise the net margin of invoice + reversal
            # wouldn't be zero.
            move = move.with_company(move.company_id)
            for line in move.invoice_line_ids:
                if line.display_type != "product" or not line.product_id:
                    continue
                vals = line._get_frozen_historical_cost_vals()
                if vals:
                    lines_by_vals[tuple(sorted(vals.items()))] |= line
        for vals_items, lines in lines_by_vals.items():
            lines._write_historical_cost(dict(vals_items))

    def button_draft(self):
        res = super().button_draft()
        self.line_ids._clear_historical_cost()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self.line_ids._clear_historical_cost()
        return res
