from unittest.mock import patch

from odoo.tests import tagged

from .common import TestStockValuationUXCommon


@tagged("post_install", "-at_install")
class TestMigratedValuationCogs(TestStockValuationUXCommon):
    """Invoicing in v19 a move whose valuation was already booked in v18
    (``stock_valuation_migrated=True``) must not generate the anglo-saxon COGS again: that
    would double the accounting impact. See task 70174 / PR 990."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.product_standard_auto

    def _stock_move(self, migrated):
        # The COGS is valued from the delivery, so it has to be done and with stock behind it.
        self._make_in_move(self.product, 2.0, 10.0)
        move = self._make_out_move(self.product, 1.0)
        move.stock_valuation_migrated = migrated
        return move

    def _cogs_lines(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.display_type == "cogs")

    def _create_invoice_linked_to(self, stock_move):
        """Create and post a customer invoice whose only product line is linked to
        ``stock_move``, patching ``_compute_cogs_move_ids``, which is what ``sale_stock``
        provides in production and what the COGS pruning consumes."""
        move_line_cls = type(self.env["account.move.line"])
        original = move_line_cls._compute_cogs_move_ids

        def _patched(records):
            original(records)
            for line in records:
                line.cogs_move_ids |= stock_move

        with patch.object(move_line_cls, "_compute_cogs_move_ids", _patched):
            return self._create_invoice(product=self.product, quantity=1.0, price_unit=20.0)

    def test_migrated_move_does_not_generate_cogs(self):
        invoice = self._create_invoice_linked_to(self._stock_move(migrated=True))
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(
            self._cogs_lines(invoice),
            "Un movimiento valorizado en la v18 no debe generar COGS al facturar en v19.",
        )

    def test_non_migrated_move_generates_cogs(self):
        invoice = self._create_invoice_linked_to(self._stock_move(migrated=False))
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(
            self._cogs_lines(invoice),
            "Un movimiento normal de v19 debe seguir generando su COGS al facturar.",
        )
