from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestValuationReportStockMoveTypes(TestStockValuationCommon):
    """The Stock Move Types filter narrows the Stock Moves origin of the variation.

    Scenario: an unaccounted receipt (purchase, +100) and an unaccounted inventory
    adjustment (-20), both of the periodic standard cost product.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.receipt = self._make_in_move(self.product_standard, 10, 10)
        # A real receipt carries no manual adjustment; the helper uses it to value.
        self.env["product.value"].search([("move_id", "=", self.receipt.id)]).unlink()
        self.adjustment = self._make_out_move(self.product_standard, 2, location_dest_id=self.inventory_location.id)
        self.adjustment.is_inventory = True

    def _data(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]

    def _variation(self, **kwargs):
        return self._data(**kwargs)["stock_variation"]["value"]

    def test_each_type_shows_only_its_moves(self):
        self.assertAlmostEqual(self._variation(stock_move_types=["purchase"]), 100.0)
        # The section adds up the debit of both legs, so the -20 shows as 20.
        self.assertAlmostEqual(self._variation(stock_move_types=["inventory"]), 20.0)
        self.assertAlmostEqual(self._variation(stock_move_types=["scrap"]), 0.0)
        self.assertAlmostEqual(
            self._variation(stock_move_types=["purchase", "inventory"]),
            self._variation(line_types=["stock_move"]),
        )

    def test_forces_the_stock_moves_origin(self):
        """With a cost change pending, a Product Value line type is ignored: the filter
        only applies to stock moves."""
        self.product_standard.standard_price = 13.0
        self.assertAlmostEqual(
            self._variation(line_types=["product_value"], stock_move_types=["purchase"]),
            100.0,
        )

    def test_does_not_touch_the_initial_balance(self):
        self.assertAlmostEqual(
            self._data(stock_move_types=["inventory"])["initial_balance"]["value"],
            self._data()["initial_balance"]["value"],
        )

    def test_drilldown_brings_only_the_filtered_moves(self):
        action = self.report.action_open_variation_stock_moves(
            self.account_stock_valuation.id, filters={"stock_move_types": ["inventory"]}
        )
        self.assertEqual(self.env["stock.move"].search(action["domain"]), self.adjustment)

    def test_closing_books_and_links_only_the_filtered_moves(self):
        self.company.action_close_stock_valuation(auto_post=True, stock_move_types=["inventory"])
        self.assertTrue(self.adjustment.account_move_id)
        self.assertFalse(self.receipt.account_move_id)
        self.assertAlmostEqual(self._variation(), 100.0, msg="The receipt stays pending")
