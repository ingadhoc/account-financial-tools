import unittest

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestMigratedValuationCogsE2E(TestStockValuationCommon):
    """Flujo real venta -> entrega -> factura con ``sale_stock``, sin parchear el
    vínculo línea-de-factura <-> stock.move (lo aporta ``sale_stock`` de verdad).

    Simula el escenario migrado marcando la entrega con
    ``stock_valuation_migrated=True`` (lo que dejaría el post-migration 18->19) y
    verifica que facturar en v19 no vuelve a generar el COGS. Ver tarea 70174."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        installed = cls.env["ir.module.module"].search([("name", "=", "sale_stock"), ("state", "=", "installed")])
        if not installed:
            raise unittest.SkipTest("sale_stock no está instalado en esta base")
        cls.product = cls.product_standard_auto
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "E2E Customer",
                "company_id": cls.company.id,
            }
        )

    def _sell_and_deliver(self, qty=1.0, price=20.0):
        # Stock a mano para poder entregar.
        self._make_in_move(self.product, qty, unit_cost=10.0, create_picking=True)
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()
        picking = sale_order.picking_ids
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model"):
            wizard = Form(self.env[result["res_model"]].with_context(**result.get("context", {}))).save()
            wizard.process()
        return sale_order

    def _invoice(self, sale_order):
        invoice = sale_order._create_invoices()
        invoice.action_post()
        return invoice

    def _cogs_lines(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.display_type == "cogs")

    def test_e2e_normal_flow_generates_cogs(self):
        sale_order = self._sell_and_deliver()
        invoice = self._invoice(sale_order)
        # El link real de sale_stock tiene que existir (no lo parcheamos).
        self.assertTrue(
            invoice.invoice_line_ids._get_stock_moves(),
            "sale_stock debe vincular la línea de factura con el movimiento de entrega.",
        )
        self.assertTrue(
            self._cogs_lines(invoice),
            "El flujo normal de v19 debe generar el COGS al facturar.",
        )

    def test_e2e_migrated_move_no_cogs(self):
        sale_order = self._sell_and_deliver()
        delivery_moves = sale_order.order_line.move_ids
        self.assertTrue(delivery_moves, "La entrega tiene que haber creado movimientos.")
        delivery_moves.stock_valuation_migrated = True
        invoice = self._invoice(sale_order)
        self.assertTrue(
            invoice.invoice_line_ids._get_stock_moves() & delivery_moves,
            "El link sale_stock línea<->movimiento debe seguir existiendo.",
        )
        self.assertFalse(
            self._cogs_lines(invoice),
            "Un movimiento valorizado en v18 no debe re-generar COGS al facturar en v19.",
        )
