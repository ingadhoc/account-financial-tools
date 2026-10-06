from datetime import timedelta

from odoo import Command, fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestProductValueBooking(TestStockValuationCommon):
    """Booking selected value adjustments from the Value Adjustments list: each one books
    exactly what it added to the inventory, and none can be booked twice.

    Scenario: an unaccounted receipt of 10 units at a standard cost of 10 (moves
    contribution = 100) plus a cost change from 10 to 13 (value adjustment = 30).
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move = self._make_in_move(self.product_standard, 10, 10)
        # A real receipt carries no manual adjustment; the helper uses it to value.
        self.env["product.value"].search([("move_id", "=", self.move.id)]).unlink()
        self.product_standard.standard_price = 13.0
        self.price_change = self._last_price_change(self.product_standard)

    def _last_price_change(self, product):
        return self.env["product.value"].search(
            [("product_id", "=", product.id), ("move_id", "=", False)], order="id desc", limit=1
        )

    def _wizard(self, product_values):
        action = product_values.action_value_product_values()
        return self.env["stock.move.valuation"].with_context(**action["context"]).create({})

    def _post(self, product_values):
        action = self._wizard(product_values).action_post()
        return self.env["account.move"].browse(action["res_id"])

    def _variation(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]["stock_variation"]["value"]

    # -- Amount ----------------------------------------------------------------
    def test_price_change_books_delta_times_quantity(self):
        """A price change stores the new unit price: what it adds is 3 x 10 units."""
        wizard = self._wizard(self.price_change)
        self.assertEqual(wizard.product_value_ids, self.price_change)
        self.assertAlmostEqual(wizard.total, 30.0)
        debit_line = wizard.line_ids.filtered("debit")
        self.assertEqual(debit_line.account_id, self.account_stock_valuation)
        self.assertEqual(debit_line.product_id, self.product_standard)

    def test_price_change_uses_quantity_at_its_date(self):
        """Stock received after the price change is not revalued by it."""
        # The quantity at a date is only rebuilt from history for a date in the past, so
        # the first receipt and the price change are moved back.
        now = fields.Datetime.now()
        self.move.date = self.move.move_line_ids.date = now - timedelta(hours=2)
        self.price_change.date = now - timedelta(hours=1)
        self._make_in_move(self.product_standard, 5, 13)
        self.assertAlmostEqual(self._wizard(self.price_change).total, 30.0)

    def test_price_decrease_credits_the_valuation_account(self):
        self.product_standard.standard_price = 11.0
        wizard = self._wizard(self._last_price_change(self.product_standard))
        credit_line = wizard.line_ids.filtered("credit")
        self.assertEqual(credit_line.account_id, self.account_stock_valuation)
        self.assertAlmostEqual(credit_line.credit, 20.0)

    def test_move_adjustment_books_its_delta(self):
        """A move adjustment stores the move's total value: what it adds is new minus
        previous value. The move has to be booked first."""
        self.env["stock.move.valuation"].with_context(default_move_ids=self.move.ids).create({}).action_post()
        adjustment = self.env["product.value"].create({"move_id": self.move.id, "value": 125.0})
        self.assertAlmostEqual(self._wizard(adjustment).total, 25.0)

    def test_outgoing_move_adjustment_credits_the_valuation_account(self):
        """An outgoing move worth 5 more takes 5 more out of the inventory."""
        out_move = self._make_out_move(self.product_standard, 1)
        self.env["product.value"].search([("move_id", "=", out_move.id)]).unlink()
        self.env["stock.move.valuation"].with_context(default_move_ids=out_move.ids).create({}).action_post()
        adjustment = self.env["product.value"].create({"move_id": out_move.id, "value": out_move.value + 5.0})
        credit_line = self._wizard(adjustment).line_ids.filtered("credit")
        self.assertEqual(credit_line.account_id, self.account_stock_valuation)
        self.assertAlmostEqual(credit_line.credit, 5.0)

    # -- Posting ---------------------------------------------------------------
    def test_post_links_only_the_selected_adjustments(self):
        self.product_standard.standard_price = 15.0
        later_change = self._last_price_change(self.product_standard)
        entry = self._post(self.price_change)
        self.assertEqual(entry.state, "posted")
        self.assertAlmostEqual(sum(entry.line_ids.mapped("debit")), 30.0)
        self.assertEqual(self.price_change.account_move_id, entry)
        self.assertFalse(later_change.account_move_id, "Not selected, stays pending")
        self.assertFalse(self.move.account_move_id, "The moves are not booked")

    def test_booked_adjustment_leaves_the_pending_variation(self):
        self.assertAlmostEqual(self._variation(), 130.0)
        self._post(self.price_change)
        self.assertAlmostEqual(self._variation(), 100.0)
        self.assertAlmostEqual(self._variation(line_types=["product_value"]), 0.0)

    def test_full_closing_after_booking_books_the_rest(self):
        entry = self._post(self.price_change)
        action = self.company.action_close_stock_valuation(auto_post=True)
        closing = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(
            sum(
                closing.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation).mapped(
                    "balance"
                )
            ),
            100.0,
        )
        self.assertEqual(self.price_change.account_move_id, entry, "The closing does not re-point it")

    def test_entry_date_before_the_adjustment_raises(self):
        wizard = self._wizard(self.price_change)
        wizard.date = fields.Date.context_today(wizard) - timedelta(days=1)
        with self.assertRaises(UserError):
            wizard.action_post()

    def test_entry_date_before_an_adjustment_of_the_valued_move_raises(self):
        """Valuing a move books its pending adjustments too, so they bound the date."""
        self.env["product.value"].create({"move_id": self.move.id, "value": 125.0})
        wizard = self.env["stock.move.valuation"].with_context(default_move_ids=self.move.ids).create({})
        wizard.date = fields.Date.context_today(wizard) - timedelta(days=1)
        with self.assertRaises(UserError):
            wizard.action_post()

    def test_adjustment_of_another_company_is_refused(self):
        """The check of the list action does not cover a wizard created directly."""
        other_value = self.env["product.value"].create(
            {"product_id": self.product_standard.id, "value": 20.0, "company_id": self.other_company.id}
        )
        wizard = self.env["stock.move.valuation"].create({"product_value_ids": [Command.set(other_value.ids)]})
        with self.assertRaises(UserError):
            wizard.action_post()
        self.assertFalse(other_value.account_move_id)

    # -- No double booking -----------------------------------------------------
    def test_second_wizard_on_the_same_adjustment_cannot_post(self):
        first = self._wizard(self.price_change)
        second = self._wizard(self.price_change)
        entry = self.env["account.move"].browse(first.action_post()["res_id"])
        with self.assertRaises(UserError):
            second.action_post()
        self.assertEqual(self.price_change.account_move_id, entry)

    def test_booked_adjustments_are_excluded_with_warning(self):
        self._post(self.price_change)
        self.product_standard.standard_price = 15.0
        later_change = self._last_price_change(self.product_standard)
        wizard = self._wizard(self.price_change | later_change)
        self.assertEqual(wizard.product_value_ids, later_change)
        self.assertTrue(wizard.excluded_warning)
        self.assertIn(self.product_standard.display_name, wizard.excluded_warning)

    def test_all_adjustments_booked_raises(self):
        self._post(self.price_change)
        with self.assertRaises(UserError):
            self._wizard(self.price_change)

    def test_adjustment_of_an_unbooked_move_is_excluded(self):
        adjustment = self.env["product.value"].create({"move_id": self.move.id, "value": 125.0})
        with self.assertRaises(UserError):
            self._wizard(adjustment)
        wizard = self._wizard(adjustment | self.price_change)
        self.assertEqual(wizard.product_value_ids, self.price_change)
        self.assertTrue(wizard.excluded_warning)

    def test_valuing_a_move_links_its_pending_adjustments(self):
        """The move's value already carries its adjustments, so valuing the move books
        them: left pending, they would be booked again."""
        adjustment = self.env["product.value"].create({"move_id": self.move.id, "value": 125.0})
        action = self.env["stock.move.valuation"].with_context(default_move_ids=self.move.ids).create({}).action_post()
        self.assertEqual(adjustment.account_move_id.id, action["res_id"])
        with self.assertRaises(UserError):
            self._wizard(adjustment)

    # -- Action entry point ----------------------------------------------------
    def test_action_opens_the_wizard(self):
        action = self.price_change.action_value_product_values()
        self.assertEqual(action["res_model"], "stock.move.valuation")
        self.assertEqual(action["context"]["default_product_value_ids"], self.price_change.ids)
