from odoo import Command
from odoo.tests import tagged

from .common import TestStockValuationUXCommon


class AccrualStockLinesMixin:
    """The stock lines of an accrual entry name their product, as the closing does on
    its valuation lines; the counterpart stays grouped by account."""

    def _set_products(self):
        self.products = self.product_standard_auto | self.product_fifo_auto

    def _validate(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True
        picking._action_done()

    def _accrual_entry(self):
        data = self.company._get_accrual_data()
        entries = self.env["account.move"].union(*(vals["move"] for vals in data.values()))
        self.assertTrue(entries, "Moved and not invoiced: there is something to accrue")
        # Each accrual comes with its reversal; the reversal copies the lines.
        return entries.filtered(lambda entry: not entry.reversed_entry_id)

    def _stock_lines(self):
        return self._accrual_entry().line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)

    def _counterpart_lines(self):
        raise NotImplementedError

    def _assert_stock_lines_name_their_product(self):
        stock_lines = self._stock_lines()
        self.assertEqual(len(stock_lines), 2, "One stock line per order line")
        self.assertEqual(stock_lines.product_id, self.products)

    def _assert_counterpart_stays_grouped(self):
        counterpart_lines = self._counterpart_lines()
        self.assertEqual(len(counterpart_lines), 1, "Same account: one line")
        self.assertFalse(counterpart_lines.product_id)


@tagged("post_install", "-at_install")
class TestAccrualStockLinesSale(AccrualStockLinesMixin, TestStockValuationUXCommon):
    """Delivered and not invoiced."""

    def setUp(self):
        super().setUp()
        if "sale_id" not in self.env["stock.picking"]._fields:
            self.skipTest("sale_stock is not installed")
        self._set_products()
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
        self._validate(order.picking_ids)

    def _counterpart_lines(self):
        return self._accrual_entry().line_ids.filtered(
            lambda line: line.display_type == "cogs" and line.account_id != self.account_stock_valuation
        )

    def test_stock_lines_name_their_product(self):
        self._assert_stock_lines_name_their_product()

    def test_counterpart_stays_grouped(self):
        self._assert_counterpart_stays_grouped()


@tagged("post_install", "-at_install")
class TestAccrualStockLinesPurchase(AccrualStockLinesMixin, TestStockValuationUXCommon):
    """Received and not billed."""

    def setUp(self):
        super().setUp()
        PurchaseOrder = self.env.get("purchase.order")
        if PurchaseOrder is None or "picking_ids" not in PurchaseOrder._fields:
            self.skipTest("purchase_stock is not installed")
        self._set_products()
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    Command.create({"product_id": product.id, "product_qty": 2.0, "price_unit": 10.0})
                    for product in self.products
                ],
            }
        )
        order.button_confirm()
        self._validate(order.picking_ids)

    def _counterpart_lines(self):
        return self._accrual_entry().line_ids.filtered(
            lambda line: line.account_id != self.account_stock_valuation and line.credit
        )

    def test_stock_lines_name_their_product(self):
        self._assert_stock_lines_name_their_product()

    def test_counterpart_stays_grouped(self):
        self._assert_counterpart_stays_grouped()
