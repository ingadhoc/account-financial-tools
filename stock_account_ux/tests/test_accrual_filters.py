from odoo import Command
from odoo.tests import tagged

from .common import TestStockValuationUXCommon


@tagged("post_install", "-at_install")
class TestAccrualFilters(TestStockValuationUXCommon):
    """The report filters apply to the Accruals section too: a product filter shows the
    accruals of those products, in the report and in the entry generated with it. The
    Movement Type filter leaves them out, as they are neither stock moves nor value
    adjustments.

    Scenario: two products delivered and not invoiced, so each one has something to
    accrue.
    """

    def setUp(self):
        super().setUp()
        if "sale_id" not in self.env["stock.picking"]._fields:
            self.skipTest("sale_stock is not installed")
        self.products = self.product_standard_auto | self.product_fifo_auto
        for product in self.products:
            self._make_in_move(product, 5, 10)
        customer = self.env["res.partner"].create({"name": "Customer"})
        order = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "order_line": [
                    Command.create({"product_id": product.id, "product_uom_qty": 2.0, "price_unit": 20.0})
                    for product in self.products
                ],
            }
        )
        order.action_confirm()
        for move in order.picking_ids.move_ids:
            move.quantity = move.product_uom_qty
        order.picking_ids.move_ids.picked = True
        order.picking_ids._action_done()
        self.report = self.env["account.stock.valuation.report"]

    def _data(self, **filters):
        return self.report.get_report_values(**filters)["data"]

    def test_product_filter_scopes_the_accruals(self):
        full = self._data()["accrual"]["value"]
        by_product = [self._data(product_ids=product.ids)["accrual"]["value"] for product in self.products]
        self.assertTrue(all(by_product), "Each product has its own accrual")
        self.assertAlmostEqual(sum(by_product), full)

    def test_filter_all_matches_no_filter(self):
        base = self._data()
        filtered = self._data(product_ids=self.products.ids)
        for section in ("accrual", "stock_variation"):
            self.assertAlmostEqual(base[section]["value"], filtered[section]["value"], msg=section)

    def test_movement_type_filter_leaves_the_accruals_out(self):
        self.assertNotIn("accrual", self._data(line_types=["stock_move"]))

    def test_partial_closing_books_the_accruals_of_its_products(self):
        product = self.product_standard_auto
        before = self.env["account.move"].search([])
        self.company.action_close_stock_valuation(product_ids=product.ids, auto_post=True, include_accruals=True)
        accrual_entries = self.env["account.move"].search(
            [("id", "not in", before.ids), ("inventory_closing", "=", False)]
        )
        stock_lines = accrual_entries.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        self.assertTrue(stock_lines, "The accrual of the filtered product is booked")
        self.assertEqual(stock_lines.product_id, product)
