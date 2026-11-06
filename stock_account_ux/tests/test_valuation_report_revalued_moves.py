from odoo import fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


def drilldown_types(report):
    """Drill-down types offered by the variation lines of the report."""
    data = report.get_report_values()["data"]
    return {t for line in data["stock_variation"]["lines"] for t in line.get("drilldown_types", [])}


@tagged("post_install", "-at_install")
class TestValuationReportRevaluedMoves(TestStockValuationCommon):
    """Where the report puts an adjustment of value.

    Scenario: an unaccounted receipt of the periodic AVCO product, 4 units at 50 (200),
    with a value adjustment of +100 that takes it to 300.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.receipt = self._make_in_move(self.product_avco, 4, 50)
        # A real receipt carries no manual adjustment; the helper uses it to value.
        self.env["product.value"].search([("move_id", "=", self.receipt.id)]).unlink()
        self.adjustment = self.env["product.value"].create(
            {"move_id": self.receipt.id, "value": 300.0, "company_id": self.company.id}
        )
        self.account = self.account_stock_valuation.id

    def _variation(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]["stock_variation"]["value"]

    def _drilldown(self, method, **filters):
        action = getattr(self.report, method)(self.account, filters=filters)
        return self.env[action["res_model"]].search(action["domain"])

    def test_revalued_move_stays_in_its_type(self):
        self.assertAlmostEqual(self._variation(), 300.0)
        self.assertAlmostEqual(self._variation(line_types=["stock_move"]), 300.0)
        self.assertAlmostEqual(self._variation(stock_move_types=["purchase"]), 300.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 0.0)
        self.assertEqual(
            self._drilldown("action_open_variation_stock_moves", stock_move_types=["purchase"]), self.receipt
        )
        self.assertFalse(self._drilldown("action_open_variation_product_values"))
        self.assertNotIn("product_value", drilldown_types(self.report))

    def test_closing_by_type_books_the_move_with_its_adjustment(self):
        action = self.company.action_close_stock_valuation(auto_post=True, stock_move_types=["purchase"])
        entry = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(sum(entry.line_ids.mapped("debit")), 300.0)
        self.assertEqual(self.receipt.account_move_id, entry)
        self.assertEqual(self.adjustment.account_move_id, entry)
        self.assertAlmostEqual(self._variation(), 0.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 0.0)

    def test_closing_product_value_leaves_the_move_adjustment(self):
        """The adjustment of an unaccounted move belongs to the Stock Moves origin, so a
        Product Value closing neither books nor links it."""
        # A cost change over 10 units in stock, 10 to 13: 30 pending in Product Value.
        standard_receipt = self._make_in_move(self.product_standard, 10)
        self.env["product.value"].search([("move_id", "=", standard_receipt.id)]).unlink()
        self.product_standard.standard_price = 13.0
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 30.0)
        action = self.company.action_close_stock_valuation(auto_post=True, line_types=["product_value"])
        entry = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(sum(entry.line_ids.mapped("debit")), 30.0)
        self.assertFalse(self.adjustment.account_move_id)
        self.assertFalse(self.receipt.account_move_id)
        self.assertAlmostEqual(self._variation(stock_move_types=["purchase"], product_ids=self.product_avco.ids), 300.0)

    def test_adjustment_of_a_booked_move_goes_to_product_value(self):
        """Once the move is booked, a later adjustment has no unaccounted move to belong
        to: it is pending in Product Value."""
        self.company.action_close_stock_valuation(auto_post=True)
        late_adjustment = self.env["product.value"].create(
            {"move_id": self.receipt.id, "value": 340.0, "company_id": self.company.id}
        )
        self.assertAlmostEqual(self._variation(line_types=["stock_move"]), 0.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 40.0)
        self.assertEqual(self._drilldown("action_open_variation_product_values"), late_adjustment)
        self.assertIn("product_value", drilldown_types(self.report))

    def test_standard_cost_move_keeps_its_value(self):
        """Under standard cost an adjustment of the move does not move the inventory, so
        the move counts what it was worth before it."""
        receipt = self._make_in_move(self.product_standard, 10)
        self.env["product.value"].search([("move_id", "=", receipt.id)]).unlink()
        self.env["product.value"].create({"move_id": receipt.id, "value": 150.0, "company_id": self.company.id})
        scope = {"categ_ids": [self.category_standard.id]}
        self.assertAlmostEqual(self._variation(line_types=["stock_move"], **scope), 100.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"], **scope), 0.0)


@tagged("post_install", "-at_install")
class TestValuationReportAdjustmentsWithNothingToBook(TestStockValuationCommon):
    """The Product Value drill-down only brings adjustments with something to book."""

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.account = self.account_stock_valuation.id

    def _product_values(self):
        action = self.report.action_open_variation_product_values(self.account)
        return self.env["product.value"].search(action["domain"])

    def _price_change(self, product, price):
        product.standard_price = price
        return self.env["product.value"].search(
            [("product_id", "=", product.id), ("move_id", "=", False)], order="id desc", limit=1
        )

    def test_cost_change_with_no_stock_is_left_out(self):
        no_stock_change = self._price_change(self.product_standard, 1000.0)
        # The receipt comes later; in a test both would share the same timestamp.
        no_stock_change.date = fields.Datetime.subtract(no_stock_change.date, days=1)
        receipt = self._make_in_move(self.product_standard, 10)
        self.env["product.value"].search([("move_id", "=", receipt.id)]).unlink()
        self.assertNotIn(no_stock_change, self._product_values())
        data = self.report.get_report_values(line_types=["stock_move"])["data"]
        drilldown_types = {t for line in data["stock_variation"]["lines"] for t in line.get("drilldown_types", [])}
        self.assertNotIn("product_value", drilldown_types)

    def test_cost_change_with_stock_is_kept(self):
        receipt = self._make_in_move(self.product_standard, 10)
        self.env["product.value"].search([("move_id", "=", receipt.id)]).unlink()
        change = self._price_change(self.product_standard, 13.0)
        self.assertIn(change, self._product_values())
        self.assertIn("product_value", drilldown_types(self.report))
