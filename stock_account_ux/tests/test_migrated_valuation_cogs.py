from unittest.mock import patch

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMigratedValuationCogs(TestStockValuationCommon):
    """Al facturar en v19 un movimiento cuya valorización ya se contabilizó en la
    v18 (``stock_valuation_migrated=True``), no debe volver a generarse el COGS
    anglosajón: eso duplicaría el impacto contable. Ver tarea 70174 / PR 990."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.product_standard_auto

    def _stock_move(self, migrated):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "product_uom": self.uom.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
            }
        )
        move.stock_valuation_migrated = migrated
        return move

    def _cogs_lines(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.display_type == "cogs")

    def _create_invoice_linked_to(self, stock_move):
        """Crea y postea una factura de venta cuya única línea de producto queda
        vinculada a ``stock_move`` (parcheando ``_get_stock_moves``, que es lo que
        aporta ``sale_stock`` en producción y lo que consume la poda del COGS)."""
        move_line_cls = type(self.env["account.move.line"])
        original = move_line_cls._get_stock_moves

        def _patched(records):
            return original(records) | stock_move

        with patch.object(move_line_cls, "_get_stock_moves", _patched):
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
