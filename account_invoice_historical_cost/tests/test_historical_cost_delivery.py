# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestHistoricalCostDelivery(TestStockValuationCommon):
    """Requires `sale`/`sale_stock` installed: they're what makes
    `account.move.line._get_stock_moves()` resolve `sale_line_ids.move_ids`,
    which is what our hook and the congelamiento formula rely on."""

    def _confirm_sale_order(self, order):
        # `ignore_exception` only exists if the optional OCA `sale_exception`
        # module is installed (it isn't in every build); bypass its
        # confirmation blocker only when the field is actually there.
        if "ignore_exception" in order._fields:
            order.ignore_exception = True
        order.action_confirm()

    def _confirm_and_deliver(self, product, quantity):
        product.invoice_policy = "order"
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": quantity,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        self._confirm_sale_order(order)
        picking = order.picking_ids
        picking.move_ids.quantity = quantity
        picking.move_ids.picked = True
        picking.button_validate()
        return order

    def _invoice_order(self, order):
        invoice = order._create_invoices()
        invoice.action_post()
        return invoice

    def _product_line(self, invoice):
        return invoice.line_ids.filtered(lambda l: l.display_type == "product")

    def test_ac2_ac3_delivery_before_invoice(self):
        product = self.product_fifo
        self._make_in_move(product, 10, unit_cost=100)
        self._make_in_move(product, 10, unit_cost=150)

        order = self._confirm_and_deliver(product, 6)
        invoice = self._invoice_order(order)
        line = self._product_line(invoice)

        self.assertFalse(line.historical_cost_provisional)
        # Consumes the first FIFO layer (cost 100), not product.standard_price
        # (which FIFO already recomputed against the remaining layer).
        self.assertAlmostEqual(line.historical_cost, 6 * 100)

    def test_ac4_complete_on_delivery(self):
        product = self.product_standard
        product.standard_price = 100.0
        product.invoice_policy = "order"

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 5,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        self._confirm_sale_order(order)

        invoice = self._invoice_order(order)
        line = self._product_line(invoice)
        self.assertTrue(line.historical_cost_provisional)
        self.assertAlmostEqual(line.historical_cost, 5 * 100.0)

        product.standard_price = 200.0

        picking = order.picking_ids
        picking.move_ids.quantity = 5
        picking.move_ids.picked = True
        picking.button_validate()

        self.assertFalse(line.historical_cost_provisional)
        # Completed from the real stock.move.value — for a `standard`
        # cost_method product, that value is computed against the cost
        # in effect AT DELIVERY TIME (200), not the invoice-time estimate
        # (100). Completing with the real value is the whole point of D1-c;
        # here the real value happens to have moved too.
        self.assertAlmostEqual(line.historical_cost, 5 * 200.0)

    def test_ac3_divergence_after_delivery_real_time(self):
        product = self.product_standard_auto  # real_time valuation
        product.standard_price = 100.0
        product.invoice_policy = "order"

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 5,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        self._confirm_sale_order(order)

        invoice = self._invoice_order(order)
        line = self._product_line(invoice)
        self.assertTrue(line.historical_cost_provisional)
        self.assertAlmostEqual(line.historical_cost, 500.0)

        # In real_time, the core already created a COGS line for this
        # product/line pair when we posted (§2 of the spec applies
        # regardless of delivery state for real_time valuation).
        cogs_lines = invoice.line_ids.filtered(lambda l: l.display_type == "cogs" and l.cogs_origin_id == line)
        self.assertTrue(cogs_lines)
        cogs_amount_before = abs(cogs_lines[0].balance)
        self.assertAlmostEqual(cogs_amount_before, 500.0)

        product.standard_price = 200.0
        picking = order.picking_ids
        picking.move_ids.quantity = 5
        picking.move_ids.picked = True
        picking.button_validate()

        self.assertFalse(line.historical_cost_provisional)
        self.assertAlmostEqual(line.historical_cost, 1000.0)

        # The journal's COGS line is never corrected retroactively (core
        # behavior, §3) — the report now diverges from the already-posted
        # entry. This divergence is the accepted trade-off of D1 (option c),
        # documented in AC3, not a bug.
        cogs_amount_after = abs(cogs_lines[0].balance)
        self.assertAlmostEqual(cogs_amount_after, cogs_amount_before)
        self.assertNotAlmostEqual(line.historical_cost, cogs_amount_after)

    def test_ac16_immutable_after_later_valuation_adjustment(self):
        product = self.product_fifo
        in_move = self._make_in_move(product, 10, unit_cost=100)

        order = self._confirm_and_deliver(product, 6)
        invoice = self._invoice_order(order)
        line = self._product_line(invoice)
        historical_cost_before = line.historical_cost
        self.assertTrue(historical_cost_before)

        # Adjust the valuation of the original receipt after the fact
        # (stock_account.stock.move.action_adjust_valuation flow): this must
        # NOT propagate to the already-posted invoice (§7 / AC16). To reflect
        # it, the invoice would need to go back to draft and be reposted.
        in_move.value_manual = 200 * 10

        self.assertEqual(line.historical_cost, historical_cost_before)

    def test_ac4_no_double_counting_across_partial_invoices(self):
        product = self.product_standard
        product.standard_price = 100.0
        product.invoice_policy = "order"

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 8,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )
        self._confirm_sale_order(order)

        invoice_1 = order._create_invoices(final=True)
        invoice_1.invoice_line_ids.filtered(lambda l: l.display_type == "product").quantity = 4
        invoice_1.action_post()
        line_1 = self._product_line(invoice_1)
        self.assertTrue(line_1.historical_cost_provisional)

        picking = order.picking_ids
        picking.move_ids.quantity = 8
        picking.move_ids.picked = True
        picking.button_validate()

        self.assertFalse(line_1.historical_cost_provisional)
        # 4 of the 8 delivered units belong to this invoice: not the full
        # move value, and not inflated by the other 4 units' cost.
        self.assertAlmostEqual(line_1.historical_cost, 4 * 100.0)

    def test_return_credit_note_uses_return_move_value(self):
        product = self.product_standard
        product.standard_price = 50000.0
        order = self._confirm_and_deliver(product, 1)
        invoice = self._invoice_order(order)
        line = self._product_line(invoice)
        self.assertAlmostEqual(line.historical_cost, 50000.0)

        product.standard_price = 70000.0

        return_form = Form(
            self.env["stock.return.picking"].with_context(
                active_ids=order.picking_ids.ids,
                active_id=order.picking_ids.id,
                active_model="stock.picking",
            )
        )
        return_picking = return_form.save()
        return_picking.product_return_moves.quantity = 1.0
        return_action = return_picking.action_create_returns()
        return_pick = self.env["stock.picking"].browse(return_action["res_id"])
        return_pick.move_ids.quantity = 1
        return_pick.move_ids.picked = True
        return_pick.button_validate()

        credit_note = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": 1000,
                            "sale_line_ids": [(6, 0, order.order_line.ids)],
                        },
                    )
                ],
            }
        )
        credit_note.action_post()
        credit_note_line = self._product_line(credit_note)

        # The return move valued the goods at 50.000 (the cost at delivery
        # time); the credit note must freeze that, not the 70.000 the ficha
        # had when it was posted (report._select() flips the sign later).
        self.assertAlmostEqual(credit_note_line.historical_cost, 50000.0)
