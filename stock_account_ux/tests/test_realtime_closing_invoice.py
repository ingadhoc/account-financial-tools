from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRealtimeClosingInvoice(TestStockValuationCommon):
    """Perpetual products: a delivery or receipt booked by a closing entry before its
    invoice must not be booked twice. Posting the invoice reverses the part of the
    closing it bills, in a separate entry, so the cost ends up booked by the invoice
    alone."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.product_standard_auto  # real time, standard cost 10
        cls.account_variation = cls.account_stock_valuation.account_stock_variation_id

    def setUp(self):
        super().setUp()
        self._make_in_move(self.product, 10, 10)
        self._close()
        self.assertEqual(self._valuation_balance(), 100.0)

    # -- Helpers ---------------------------------------------------------------
    def _valuation_balance(self):
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.account_stock_valuation.id),
                ("parent_state", "=", "posted"),
                ("company_id", "=", self.company.id),
            ]
        )
        return sum(lines.mapped("balance"))

    def _validate(self, picking, quantity):
        picking.move_ids.quantity = quantity
        picking.move_ids.picked = True
        picking.button_validate()

    def _skip_without(self, field, module):
        # The module does not depend on sale_stock nor purchase_stock.
        if field not in self.env["stock.move"]._fields:
            self.skipTest(f"{module} is not installed")

    def _sell(self, quantity, deliver=None):
        self._skip_without("sale_line_id", "sale_stock")
        order = self.env["sale.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": quantity})],
            }
        )
        order.action_confirm()
        self._validate(order.picking_ids, quantity if deliver is None else deliver)
        return order

    def _buy(self, quantity):
        self._skip_without("purchase_line_id", "purchase_stock")
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_qty": quantity, "price_unit": 10})
                ],
            }
        )
        order.button_confirm()
        self._validate(order.picking_ids, quantity)
        return order

    def _invoice(self, order, quantity=None, post=True):
        invoice = order._create_invoices()
        if quantity is not None:
            invoice.invoice_line_ids.quantity = quantity
        if post:
            invoice.action_post()
        return invoice

    def _bill(self, order):
        order.action_create_invoice()
        bill = order.invoice_ids
        bill.invoice_date = fields.Date.today()
        bill.action_post()
        return bill

    def _reversals(self, closing):
        return closing.reversal_move_ids.filtered(lambda entry: entry.state == "posted")

    # -- Sale ------------------------------------------------------------------
    def test_sale_invoice_reverses_closing(self):
        order = self._sell(2)
        closing = self._close()
        self.assertEqual(self._valuation_balance(), 80.0)

        invoice = self._invoice(order)
        self.assertEqual(self._valuation_balance(), 80.0, "The cost is booked once, by the invoice")

        reversal = self._reversals(closing)
        self.assertEqual(len(reversal), 1)
        self.assertEqual(reversal.move_type, "entry")
        self.assertEqual(reversal.journal_id, closing.journal_id)
        valuation_line = reversal.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        self.assertEqual(valuation_line.debit, 20.0)
        self.assertEqual(valuation_line.quantity, 2.0)
        self.assertEqual(valuation_line.product_id, self.product)
        self.assertEqual(valuation_line.cogs_origin_id, invoice.invoice_line_ids)
        variation_line = reversal.line_ids - valuation_line
        self.assertEqual(variation_line.account_id, self.account_variation)
        self.assertEqual(variation_line.credit, 20.0)

        delivery = order.picking_ids.move_ids
        self.assertEqual(delivery.account_move_id, closing, "The closing reference is kept")
        self.assertEqual(delivery.related_account_move_id, invoice, "The invoice books it now")
        self.assertIn(reversal, delivery.all_account_move_ids)

    def test_invoice_before_closing_reverses_nothing(self):
        order = self._sell(2)
        self._invoice(order)
        self.assertEqual(self._valuation_balance(), 80.0)
        self.assertFalse(self.env["account.move"].search([("reversed_entry_id", "!=", False)]))

    def test_partial_invoices_are_proportional(self):
        order = self._sell(4)
        closing = self._close()
        self.assertEqual(self._valuation_balance(), 60.0)

        self._invoice(order, quantity=1)
        self.assertEqual(self._valuation_balance(), 60.0)
        self.assertEqual(sum(self._reversals(closing).mapped("amount_total")), 10.0)

        self._invoice(order)  # the remaining 3
        self.assertEqual(self._valuation_balance(), 60.0)
        self.assertEqual(sum(self._reversals(closing).mapped("amount_total")), 40.0)

    def test_invoice_dated_before_closing_reverses_at_closing_date(self):
        order = self._sell(2)
        closing = self._close()
        invoice = self._invoice(order, post=False)
        invoice.invoice_date = fields.Date.today() - relativedelta(days=1)
        invoice.action_post()
        self.assertEqual(self._reversals(closing).date, closing.date)

    # -- Credit notes ----------------------------------------------------------
    def test_credit_note_reopens_delivery_for_a_new_closing(self):
        order = self._sell(2)
        closing = self._close()
        invoice = self._invoice(order)
        reversal = self._reversals(closing)
        self._refund(invoice)
        delivery = order.picking_ids.move_ids
        self.assertEqual(self._reversals(closing), reversal, "The credit note leaves the reversal in place")
        self.assertEqual(self._valuation_balance(), 100.0)
        self.assertFalse(delivery.related_account_move_id, "The delivery is pending again")

        new_closing = self._close()
        self.assertEqual(self._valuation_balance(), 80.0)
        self.assertEqual(delivery.account_move_id, new_closing)

        new_invoice = self._invoice(order)
        self.assertEqual(self._valuation_balance(), 80.0)
        self.assertEqual(len(self._reversals(new_closing)), 1)
        self.assertEqual(self._reversals(closing), reversal, "The first closing is not reversed twice")
        self.assertEqual(delivery.related_account_move_id, new_invoice)

    def test_credit_note_then_new_invoice(self):
        order = self._sell(2)
        closing = self._close()
        invoice = self._invoice(order)
        self._refund(invoice)

        new_invoice = self._invoice(order)
        self.assertEqual(self._valuation_balance(), 80.0, "The new invoice books the cost by itself")
        self.assertEqual(len(self._reversals(closing)), 1, "That part of the closing was already reversed")
        self.assertEqual(order.picking_ids.move_ids.related_account_move_id, new_invoice)

    # -- Back to draft ---------------------------------------------------------
    def test_invoice_back_to_draft_cancels_reversal(self):
        order = self._sell(2)
        closing = self._close()
        invoice = self._invoice(order)
        reversal = self._reversals(closing)

        invoice.button_draft()
        self.assertNotEqual(reversal.state, "posted")
        self.assertFalse(self._reversals(closing))
        self.assertEqual(self._valuation_balance(), 80.0, "The closing books the delivery again")
        self.assertEqual(order.picking_ids.move_ids.related_account_move_id, closing)

        invoice.action_post()
        self.assertEqual(len(self._reversals(closing)), 1)
        self.assertEqual(self._valuation_balance(), 80.0)

    def test_locked_reversal_is_reversed_on_back_to_draft(self):
        self.company.account_stock_journal_id.restrict_mode_hash_table = True
        order = self._sell(2)
        closing = self._close()
        invoice = self._invoice(order)
        reversal = self._reversals(closing)
        self.assertTrue(reversal.inalterable_hash)

        invoice.button_draft()
        self.assertEqual(reversal.state, "posted", "A locked entry cannot go back to draft")
        self.assertTrue(reversal.reversal_move_ids.filtered(lambda entry: entry.state == "posted"))
        self.assertEqual(self._valuation_balance(), 80.0)

        invoice.action_post()
        self.assertEqual(self._valuation_balance(), 80.0, "Its reversal does not count as reversed")

    # -- Purchase --------------------------------------------------------------
    def test_purchase_bill_reverses_closing(self):
        order = self._buy(3)
        closing = self._close()
        self.assertEqual(self._valuation_balance(), 130.0)

        bill = self._bill(order)
        self.assertEqual(self._valuation_balance(), 130.0, "The stock is booked once, by the bill")
        valuation_line = self._reversals(closing).line_ids.filtered(
            lambda line: line.account_id == self.account_stock_valuation
        )
        self.assertEqual(valuation_line.credit, 30.0)
        self.assertEqual(valuation_line.cogs_origin_id, bill.invoice_line_ids)
        self.assertEqual(order.picking_ids.move_ids.related_account_move_id, bill)
