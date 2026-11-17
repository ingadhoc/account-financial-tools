from unittest.mock import patch

from odoo.tests import tagged

from .common import TestStockValuationUXCommon


@tagged("post_install", "-at_install")
class TestMigratedValuationPurchase(TestStockValuationUXCommon):
    """Invoicing in v19 a purchase whose move was already valued in v18
    (``stock_valuation_migrated=True``), the invoice line must not debit the stock
    valuation account again —that would increase the asset twice— but the counterpart of
    the migrated valuation entry. See task 70174."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.product_standard_auto
        cls.valuation_account = cls.product.product_tmpl_id.get_product_accounts()["stock_valuation"]
        # Counterpart of the asset increase in the migrated entry (the credit): an account
        # other than the valuation one, typically a goods purchase account.
        cls.counterpart_account = cls.env["account.account"].create(
            {
                "name": "Goods Purchase",
                "code": "600700",
                "account_type": "expense",
            }
        )

    def _migrated_in_move(self, migrated=True, with_entry=True):
        """Incoming move with, optionally, the migrated valuation entry re-attached to
        ``account_move_id``: Dr valuation / Cr counterpart."""
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "uom_id": self.uom.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        if with_entry:
            entry = self.env["account.move"].create(
                {
                    "move_type": "entry",
                    "line_ids": [
                        (0, 0, {"account_id": self.valuation_account.id, "debit": 100.0, "credit": 0.0}),
                        (0, 0, {"account_id": self.counterpart_account.id, "debit": 0.0, "credit": 100.0}),
                    ],
                }
            )
            move.account_move_id = entry.id
        move.stock_valuation_migrated = migrated
        return move

    def _link_cogs_moves(self, stock_move):
        """Patch ``_compute_cogs_move_ids``, which in production comes from
        ``purchase_stock`` through ``purchase_line_id``, to link every line to ``stock_move``."""
        move_line_cls = type(self.env["account.move.line"])
        original = move_line_cls._compute_cogs_move_ids

        def _patched(records):
            original(records)
            for line in records:
                line.cogs_move_ids |= stock_move

        return patch.object(move_line_cls, "_compute_cogs_move_ids", _patched)

    def _bill_product_line(self, stock_move):
        """Create, without posting, a vendor bill with a product line linked to ``stock_move``."""
        with self._link_cogs_moves(stock_move):
            bill = self._create_bill(product=self.product, quantity=1.0, price_unit=20.0, post=False)
        return bill.invoice_line_ids

    def test_migrated_bill_line_uses_counterpart_account(self):
        line = self._bill_product_line(self._migrated_in_move(migrated=True))
        self.assertEqual(
            line.account_id,
            self.counterpart_account,
            "The bill of a move valued in v18 has to be booked to the counterpart of the "
            "migrated entry, not to the valuation account.",
        )

    def test_non_migrated_bill_line_uses_valuation_account(self):
        line = self._bill_product_line(self._migrated_in_move(migrated=False))
        self.assertEqual(
            line.account_id,
            self.valuation_account,
            "A regular v19 purchase keeps being booked to the stock valuation account, as "
            "stock_account does out of the box.",
        )

    def test_migrated_bill_price_difference_settles_on_the_counterpart(self):
        """The price difference lines of a posted bill use the line account as their
        counterpart, so the gap to the standard price is settled on the migrated counterpart
        and the valuation account is not touched."""
        price_diff_account = self.env["account.account"].create(
            {"name": "Price Difference", "code": "600800", "account_type": "expense"}
        )
        self.product.categ_id.property_price_difference_account_id = price_diff_account
        stock_move = self._migrated_in_move(migrated=True)
        bill = self._bill_product_line(stock_move).move_id
        with self._link_cogs_moves(stock_move):
            bill.action_post()
        balances = {}
        for line in bill.line_ids:
            balances[line.account_id] = balances.get(line.account_id, 0.0) + line.balance
        # Bill at 20 against a standard price of 10
        self.assertAlmostEqual(balances[price_diff_account], 10.0)
        self.assertAlmostEqual(balances[self.counterpart_account], 10.0)
        self.assertNotIn(self.valuation_account, balances)

    def test_back_to_draft_and_cancel_keep_the_migrated_value(self):
        """Odoo 20 also revalues the invoiced moves when the bill goes back to draft or is
        cancelled; the value of a migrated move comes from v18 and has to stay."""
        stock_move = self._make_in_move(self.product, 1, 10)
        stock_move.stock_valuation_migrated = True
        stock_move.value = 77.0
        bill = self._bill_product_line(stock_move).move_id
        with self._link_cogs_moves(stock_move):
            bill.action_post()
            bill.button_draft()
            self.assertEqual(stock_move.value, 77.0, "Back to draft must not revalue a migrated move.")
            bill.button_cancel()
        self.assertEqual(stock_move.value, 77.0, "Cancelling must not revalue a migrated move.")

    def test_counterpart_helper_returns_credit_account(self):
        move = self._migrated_in_move(migrated=True)
        self.assertEqual(move._get_migrated_valuation_counterpart_account(), self.counterpart_account)

    def test_counterpart_helper_without_entry_returns_empty(self):
        move = self._migrated_in_move(migrated=True, with_entry=False)
        self.assertFalse(move._get_migrated_valuation_counterpart_account())

    def test_set_value_skips_migrated_in_move_on_post_context(self):
        """En el contexto de posteo de la factura, ``_set_value`` no debe
        recomputar el ``value`` de un movimiento migrado (ya viene de la v18)."""
        move = self._migrated_in_move(migrated=True)
        move.value = 123.0
        move.with_context(skip_migrated_stock_revaluation=True)._set_value()
        self.assertEqual(move.value, 123.0, "No debe revalorizarse el movimiento migrado al postear la factura.")
