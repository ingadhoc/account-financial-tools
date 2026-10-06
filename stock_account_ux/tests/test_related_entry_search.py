from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRelatedEntrySearch(TestStockValuationCommon):
    """``related_account_move_id`` set / not set is answered in SQL
    (``_get_related_entry_domain``) and has to give the same moves as the computed field,
    which the valuation report and the closing use to find the unaccounted moves."""

    def _assert_search_matches_field(self, moves):
        Move = self.env["stock.move"]
        # The field is not stored and its dependencies miss the related invoices.
        self.env.invalidate_all()
        with_entry = Move.search([("id", "in", moves.ids), ("related_account_move_id", "!=", False)])
        without_entry = Move.search([("id", "in", moves.ids), ("related_account_move_id", "=", False)])
        self.env.invalidate_all()
        self.assertEqual(with_entry, moves.filtered("related_account_move_id"))
        self.assertEqual(without_entry, moves - with_entry)

    def _deliver(self, picking):
        picking.move_ids.write({"quantity": 1.0, "picked": True})
        picking._action_done()
        return picking.move_ids

    def _sale_delivery(self, product):
        if "sale_id" not in self.env["stock.picking"]._fields:
            self.skipTest("sale_stock is not installed")
        self._make_in_move(product, 1, 10)
        customer = self.env["res.partner"].create({"name": "Customer"})
        order = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1.0, "price_unit": 20.0})],
            }
        )
        order.action_confirm()
        return order, self._deliver(order.picking_ids)

    def _invoice_order(self, order):
        """Posted invoice linked to the order lines. Not through ``_create_invoices``: other
        modules change when an order has something to invoice, which is not under test."""
        line = order.order_line
        invoice = self._create_invoice(product=line.product_id, price_unit=line.price_unit, post=False)
        invoice.invoice_line_ids.sale_line_ids = line
        invoice.action_post()
        return invoice

    def _purchase_receipt(self, product):
        PurchaseOrder = self.env.get("purchase.order")
        if PurchaseOrder is None or "picking_ids" not in PurchaseOrder._fields:
            self.skipTest("purchase_stock is not installed")
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [Command.create({"product_id": product.id, "product_qty": 1.0, "price_unit": 10.0})],
            }
        )
        order.button_confirm()
        return order, self._deliver(order.picking_ids)

    def test_closing_entry_and_revaluation(self):
        move_standard = self._make_in_move(self.product_standard, 10, 10)
        move_avco = self._make_in_move(self.product_avco, 4, 25)
        moves = move_standard | move_avco
        self._assert_search_matches_field(moves)
        self.assertFalse(moves.filtered("related_account_move_id"))

        closing = self._close()
        self._assert_search_matches_field(moves)
        self.assertEqual(moves.filtered("related_account_move_id"), moves)

        # A closing sent back to draft books nothing, a booked revaluation does.
        move_avco.value_manual = 130.0
        revaluation = self._close()
        closing.button_draft()
        self._assert_search_matches_field(moves)
        self.assertEqual(moves.filtered("related_account_move_id"), move_avco)
        revaluation.button_draft()
        self._assert_search_matches_field(moves)
        self.assertFalse(moves.filtered("related_account_move_id"))

    def test_sale_invoice_books_real_time_delivery_only(self):
        order_auto, delivery_auto = self._sale_delivery(self.product_standard_auto)
        order_periodic, delivery_periodic = self._sale_delivery(self.product_standard)
        moves = delivery_auto | delivery_periodic
        self._assert_search_matches_field(moves)
        self.assertFalse(moves.filtered("related_account_move_id"))

        invoice = self._invoice_order(order_auto)
        self._invoice_order(order_periodic)
        self._assert_search_matches_field(moves)
        # Under periodic valuation the invoice books no cost: the move waits for the closing.
        self.assertEqual(moves.filtered("related_account_move_id"), delivery_auto)
        self.assertEqual(self.env["stock.move"].search([("related_account_move_id", "=", invoice.id)]), delivery_auto)

    def test_purchase_bill_books_real_time_receipt(self):
        order, receipt = self._purchase_receipt(self.product_standard_auto)
        self._assert_search_matches_field(receipt)

        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_date = fields.Date.today()
        self._assert_search_matches_field(receipt)
        self.assertFalse(receipt.related_account_move_id, "A draft bill books nothing")

        bill.action_post()
        self._assert_search_matches_field(receipt)
        self.assertEqual(receipt.related_account_move_id, bill)
        self.assertEqual(self.env["stock.move"].search([("related_account_move_id", "=", bill.id)]), receipt)

    def test_set_not_set_search_does_not_compute_the_field(self):
        """Computing the field resolves the related invoices move by move, which ran a big
        base out of memory: the set / not set search must not touch it."""
        self._make_in_move(self.product_standard_auto, 1, 10)
        move_class = type(self.env["stock.move"])
        with patch.object(move_class, "_get_related_invoices", side_effect=AssertionError("computed")):
            self.env["stock.move"].search([("related_account_move_id", "=", False)])
            self.env["stock.move"].search([("related_account_move_id", "!=", False)])
