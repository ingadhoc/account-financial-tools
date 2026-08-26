from odoo import models


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
