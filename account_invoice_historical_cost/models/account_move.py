# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        # Must run before super(), which is where stock_account creates the
        # COGS lines (_stock_account_prepare_realtime_out_lines_vals). This
        # way _get_posted_cogs_value() never sees this invoice's own COGS
        # lines, so the frozen value is bit-identical to the one the core
        # uses to build them.
        self._freeze_historical_cost()
        return super()._post(soft)

    def _freeze_historical_cost(self):
        for move in self:
            if not move.is_sale_document(include_receipts=True):
                continue
            # Deliberately NOT excluded for move_reverse_cancel (unlike
            # stock_account._post): the cancellation credit note also needs
            # its cost frozen, otherwise the net margin of invoice + reversal
            # wouldn't be zero.
            move = move.with_company(move.company_id)
            anglo_saxon_price_ctx = move._get_anglo_saxon_price_ctx()
            for line in move.invoice_line_ids:
                if line.display_type != "product" or not line.product_id:
                    continue
                line._freeze_historical_cost(anglo_saxon_price_ctx)

    def button_draft(self):
        res = super().button_draft()
        self.line_ids._clear_historical_cost()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self.line_ids._clear_historical_cost()
        return res
