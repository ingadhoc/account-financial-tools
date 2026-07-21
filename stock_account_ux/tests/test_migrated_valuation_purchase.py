from unittest.mock import patch

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMigratedValuationPurchase(TestStockValuationCommon):
    """Al facturar en v19 una compra cuyo movimiento ya se valorizó en la v18
    (``stock_valuation_migrated=True``), la línea de factura no debe volver a
    debitar la cuenta de valorización de stock (alta del activo duplicada): debe
    imputarse a la contrapartida del asiento de valorización migrado. Ver tarea
    70174."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.product_standard_auto
        cls.valuation_account = cls.product.product_tmpl_id.get_product_accounts()["stock_valuation"]
        # Contrapartida del alta de activo del asiento migrado (el crédito): una
        # cuenta distinta de la de valorización, típicamente compra de mercadería.
        cls.counterpart_account = cls.env["account.account"].create(
            {
                "name": "Compra de mercadería",
                "code": "600700",
                "account_type": "expense",
            }
        )

    def _migrated_in_move(self, migrated=True, with_entry=True):
        """Movimiento de entrada con (opcionalmente) el asiento de valorización
        migrado reenganchado en ``account_move_id``: Dr valorización / Cr
        contrapartida."""
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
        """Crea (sin postear) una factura de proveedor con una línea de producto
        vinculada a ``stock_move`` (parcheando ``_get_stock_moves``, que en
        producción aporta ``purchase_stock`` vía ``purchase_line_id``)."""
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
            "La factura de un movimiento valorizado en la v18 debe imputarse a la "
            "contrapartida del asiento migrado, no a la cuenta de valorización.",
        )

    def test_non_migrated_bill_line_uses_valuation_account(self):
        line = self._bill_product_line(self._migrated_in_move(migrated=False))
        self.assertEqual(
            line.account_id,
            self.valuation_account,
            "Una compra normal de v19 debe seguir imputándose a la cuenta de "
            "valorización de stock (comportamiento de fábrica de stock_account).",
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
