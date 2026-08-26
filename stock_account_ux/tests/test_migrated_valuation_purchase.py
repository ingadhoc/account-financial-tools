from unittest.mock import patch

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMigratedValuationPurchase(TestStockValuationCommon):
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
                "product_uom": self.uom.id,
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

    def _bill_product_line(self, stock_move):
        """Create, without posting, a vendor bill with a product line linked to
        ``stock_move``, patching ``_get_stock_moves``, which in production comes from
        ``purchase_stock`` through ``purchase_line_id``."""
        move_line_cls = type(self.env["account.move.line"])
        original = move_line_cls._get_stock_moves

        def _patched(records):
            return original(records) | stock_move

        with patch.object(move_line_cls, "_get_stock_moves", _patched):
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
