from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRelatedEntrySearch(TestStockValuationCommon):
    """``related_account_move_id`` is stored: searching it set / not set reads the column,
    which has to agree with what the compute gives, as the valuation report and the
    closing use it to find the unaccounted moves. The compute runs on the dependencies,
    the related invoices included, so a posted invoice has to show up without any
    recompute from the test."""

    def _assert_search_matches_field(self, moves):
        Move = self.env["stock.move"]
        self.env.invalidate_all()
        with_entry = Move.search([("id", "in", moves.ids), ("related_account_move_id", "!=", False)])
        without_entry = Move.search([("id", "in", moves.ids), ("related_account_move_id", "=", False)])
        self.env.invalidate_all()
        self.assertEqual(with_entry, moves.filtered("related_account_move_id"))
        self.assertEqual(without_entry, moves - with_entry)

    def _related_entry_state(self, move):
        """What the compute sees for ``move``, to tell why an assertion failed on a base
        with more modules installed."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT category.property_valuation FROM product_category category WHERE category.id = %s",
            [move.product_id.categ_id.id],
        )
        category_column = self.env.cr.fetchone()[0]
        return (
            f"company={move.company_id.id} env_company={self.env.company.id}"
            f" product_company={move.product_id.company_id.id}"
            f" valuation={move.product_id.with_company(move.company_id).valuation}"
            f" category_column={category_column}"
            f" real_time={bool(move._filter_real_time_valuation())}"
            f" invoice_by_picking={move._get_related_invoice_by_picking()}"
            f" account_move={move.account_move_id.id} picking={move.picking_id.id}"
        )

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
        """Resolving the related invoices move by move ran a big base out of memory: the
        set / not set search reads the stored column and must not compute anything."""
        self._make_in_move(self.product_standard_auto, 1, 10)
        move_class = type(self.env["stock.move"])
        with patch.object(move_class, "_get_related_invoices", side_effect=AssertionError("computed")):
            self.env["stock.move"].search([("related_account_move_id", "=", False)])
            self.env["stock.move"].search([("related_account_move_id", "!=", False)])

    def test_valuation_is_read_in_the_move_company(self):
        """The product valuation depends on the company: the compute must read it in the
        move's company, not in the one of whoever triggers it."""
        self.category_standard_auto.with_company(self.other_company).property_valuation = "periodic"
        self.category_standard.with_company(self.other_company).property_valuation = "real_time"
        order_auto, delivery_auto = self._sale_delivery(self.product_standard_auto)
        order_periodic, delivery_periodic = self._sale_delivery(self.product_standard)
        invoice = self._invoice_order(order_auto)
        self._invoice_order(order_periodic)
        moves = delivery_auto | delivery_periodic

        moves.with_company(self.other_company)._recompute_related_account_move()
        self._assert_search_matches_field(moves)
        self.assertEqual(delivery_auto.related_account_move_id, invoice, self._related_entry_state(delivery_auto))
        self.assertFalse(delivery_periodic.related_account_move_id)

    def test_company_default_valuation_change(self):
        """A category with no valuation of its own takes the company's: changing it has to
        recompute the related entry of the moves already invoiced."""
        self.company.inventory_valuation = "periodic"
        category = self.env["product.category"].create({"name": "Company Default", "property_cost_method": "standard"})
        product = self.env["product.product"].create(
            {**self.product_common_vals, "name": "Company Default Product", "categ_id": category.id}
        )
        order, delivery = self._sale_delivery(product)
        invoice = self._invoice_order(order)
        self.assertFalse(delivery.related_account_move_id)

        self.company.inventory_valuation = "real_time"
        self.assertEqual(product.valuation, "real_time")
        self._assert_search_matches_field(delivery)
        self.assertEqual(delivery.related_account_move_id, invoice, self._related_entry_state(delivery))

        self.company.inventory_valuation = "periodic"
        self._assert_search_matches_field(delivery)
        self.assertFalse(delivery.related_account_move_id)
