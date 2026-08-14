from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClosingByLineType(TestStockValuationCommon):
    """The entry generated from the report has to honour the Movement Type filter: book
    only the filtered origin of the variation and leave the other one pending.

    Scenario: an unaccounted receipt (moves contribution = 100) plus a cost change (value
    adjustments contribution = 30). Total variation = 130.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move = self._make_in_move(self.product_standard, 10, 10)  # 10 units at a standard cost of 10
        # A real receipt carries no manual adjustment; the helper uses it to value.
        self.env["product.value"].search([("move_id", "=", self.move.id)]).unlink()
        # Cost change: 10 to 13 over 10 units = 30 contributed by the value adjustment.
        self.product_standard.standard_price = 13.0
        self.price_change = self.env["product.value"].search(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)],
            order="id desc",
            limit=1,
        )

    def _close(self, line_types=None, auto_post=True):
        action = self.company.action_close_stock_valuation(auto_post=auto_post, line_types=line_types)
        return self.env["account.move"].browse(action["res_id"])

    def _total(self, entry):
        return sum(entry.line_ids.mapped("debit"))

    def _variation(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]["stock_variation"]["value"]

    def test_scenario(self):
        """Starting point: the variation is made of 100 from moves and 30 from value
        adjustments."""
        self.assertAlmostEqual(self._variation(), 130.0)
        self.assertAlmostEqual(self._variation(line_types=["stock_move"]), 100.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 30.0)

    # -- Closing per origin ----------------------------------------------------
    def test_closing_only_stock_moves(self):
        entry = self._close(line_types=["stock_move"])
        self.assertAlmostEqual(self._total(entry), 100.0, msg="Only the moves portion")
        # It links the move it booked...
        self.assertEqual(self.move.account_move_id, entry)
        # ...and NOT the value adjustment, which stays pending.
        self.assertFalse(self.price_change.account_move_id)
        self.assertAlmostEqual(self._variation(), 30.0, msg="The value adjustment stays pending")

    def test_closing_only_product_values(self):
        entry = self._close(line_types=["product_value"])
        self.assertAlmostEqual(self._total(entry), 30.0, msg="Only the value adjustments portion")
        self.assertEqual(self.price_change.account_move_id, entry)
        self.assertFalse(self.move.account_move_id)
        self.assertAlmostEqual(self._variation(), 100.0, msg="The moves stay pending")

    def test_closing_both_origins_equals_full_closing(self):
        """The two origins are complementary: closing one and then the other has to leave
        the variation at zero, just like the full closing."""
        first = self._close(line_types=["stock_move"])
        second = self._close(line_types=["product_value"])
        self.assertNotEqual(first, second)
        self.assertAlmostEqual(self._total(first) + self._total(second), 130.0)
        self.assertAlmostEqual(self._variation(), 0.0)
        self.assertEqual(self.move.account_move_id, first)
        self.assertEqual(self.price_change.account_move_id, second)

    def test_closing_with_both_line_types_closes_everything(self):
        """Selecting both types means no Movement Type filter at all."""
        entry = self._close(line_types=["stock_move", "product_value"])
        self.assertAlmostEqual(self._total(entry), 130.0)
        self.assertEqual(self.move.account_move_id, entry)
        self.assertEqual(self.price_change.account_move_id, entry)
        self.assertAlmostEqual(self._variation(), 0.0)

    def test_closing_without_line_types_is_unchanged(self):
        """With no filter the closing still books everything and links both."""
        entry = self._close()
        self.assertAlmostEqual(self._total(entry), 130.0)
        self.assertEqual(self.move.account_move_id, entry)
        self.assertEqual(self.price_change.account_move_id, entry)

    def test_closing_by_line_type_combined_with_product_filter(self):
        """The Movement Type filter combines with the product one."""
        other_move = self._make_in_move(self.product_avco, 4, 25)
        self.env["product.value"].search([("move_id", "=", other_move.id)]).unlink()
        action = self.company.action_close_stock_valuation(
            auto_post=True,
            product_ids=self.product_standard.ids,
            line_types=["stock_move"],
        )
        entry = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(self._total(entry), 100.0, msg="Only the filtered product")
        self.assertEqual(self.move.account_move_id, entry)
        self.assertFalse(other_move.account_move_id, "The other product was not closed")
        self.assertFalse(self.price_change.account_move_id, "The value adjustment stays pending")

    # -- Per-product attribution of the per-origin entry -----------------------
    def test_closing_by_origin_attributes_the_lines_by_product(self):
        """The per-origin entry is attributed too, but with the contribution of THAT origin
        (100 from moves), not with the whole pending difference (130)."""
        entry = self._close(line_types=["stock_move"])
        valuation_lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        self.assertEqual(valuation_lines.product_id, self.product_standard, "Attributed to the product")
        net = sum(valuation_lines.mapped("debit")) - sum(valuation_lines.mapped("credit"))
        self.assertAlmostEqual(net, 100.0)
        self.assertAlmostEqual(self._total(entry), 100.0, msg="The entry amount does not change")

    def test_closing_by_origin_leaves_the_rest_pending_per_product(self):
        """Once the moves origin is closed, the Initial Balance filtered by product shows
        what was booked and the variation only what stayed pending."""
        self._close(line_types=["stock_move"])
        data = self.report.get_report_values(product_ids=self.product_standard.ids)["data"]
        self.assertAlmostEqual(data["initial_balance"]["value"], 100.0)
        self.assertAlmostEqual(data["stock_variation"]["value"], 30.0, msg="The value adjustment is left")
