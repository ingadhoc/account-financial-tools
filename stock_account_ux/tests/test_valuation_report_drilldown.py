from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestValuationReportDrilldown(TestStockValuationCommon):
    """Drill-down from the valuation report to the detail behind each section. The main
    gap was the Variation, which offers no navigation at all out of the box."""

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move_standard = self._make_in_move(self.product_standard, 10, 10)
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)
        self.env["product.value"].search([("move_id", "in", (self.move_standard + self.move_avco).ids)]).unlink()
        self.account = self.account_stock_valuation

    def _records(self, action):
        """The records the user gets when opening the action."""
        return self.env[action["res_model"]].search(action["domain"])

    # -- Variation to the unaccounted moves ------------------------------------
    def test_variation_stock_moves_drilldown(self):
        action = self.report.action_open_variation_stock_moves(self.account.id)
        self.assertEqual(action["res_model"], "stock.move")
        moves = self._records(action)
        self.assertIn(self.move_standard, moves)
        self.assertIn(self.move_avco, moves)

    def test_variation_stock_moves_excludes_accounted(self):
        """Already booked moves are no longer part of the difference to adjust, so they
        must not show up."""
        self.env["stock.move.valuation"].with_context(default_move_ids=self.move_avco.ids).create({}).action_post()
        moves = self._records(self.report.action_open_variation_stock_moves(self.account.id))
        self.assertIn(self.move_standard, moves)
        self.assertNotIn(self.move_avco, moves)

    def test_variation_stock_moves_respects_report_filters(self):
        """The detail honours the report's active filters."""
        action = self.report.action_open_variation_stock_moves(
            self.account.id, filters={"categ_ids": [self.category_standard.id]}
        )
        moves = self._records(action)
        self.assertIn(self.move_standard, moves)
        self.assertNotIn(self.move_avco, moves)

    def test_variation_stock_moves_scoped_by_account(self):
        """Only the moves of products booked to THAT account."""
        other_account = self.env["account.account"].create(
            {"name": "Other Stock Valuation", "code": "110199", "account_type": "asset_current"}
        )
        self.category_avco.property_stock_valuation_account_id = other_account
        moves = self._records(self.report.action_open_variation_stock_moves(self.account.id))
        self.assertIn(self.move_standard, moves)
        self.assertNotIn(self.move_avco, moves)
        other_moves = self._records(self.report.action_open_variation_stock_moves(other_account.id))
        self.assertIn(self.move_avco, other_moves)
        self.assertNotIn(self.move_standard, other_moves)

    # -- Variation to the unaccounted value adjustments ------------------------
    def test_variation_product_values_drilldown(self):
        self.product_standard.standard_price = 13.0
        price_change = self.env["product.value"].search(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)],
            order="id desc",
            limit=1,
        )
        self.move_avco.value_manual = 130.0
        move_adjustment = self.env["product.value"].search(
            [("move_id", "=", self.move_avco.id)], order="id desc", limit=1
        )
        action = self.report.action_open_variation_product_values(self.account.id)
        self.assertEqual(action["res_model"], "product.value")
        adjustments = self._records(action)
        self.assertIn(price_change, adjustments, "Cost change on the product")
        self.assertIn(move_adjustment, adjustments, "Value adjustment of a move")

    def test_variation_product_values_excludes_booked(self):
        self.product_standard.standard_price = 13.0
        price_change = self.env["product.value"].search(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)],
            order="id desc",
            limit=1,
        )
        self._close()
        self.assertTrue(price_change.account_move_id, "The closing booked it")
        adjustments = self._records(self.report.action_open_variation_product_values(self.account.id))
        self.assertNotIn(price_change, adjustments)

    def test_variation_product_values_respects_report_filters(self):
        self.product_standard.standard_price = 13.0
        price_change = self.env["product.value"].search(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)],
            order="id desc",
            limit=1,
        )
        action = self.report.action_open_variation_product_values(
            self.account.id, filters={"categ_ids": [self.category_avco.id]}
        )
        self.assertNotIn(price_change, self._records(action))

    # -- Initial Balance to the General Ledger ---------------------------------
    def test_account_ledger_drilldown(self):
        action = self.report.action_open_account_ledger(self.account.id, "2026-07-31")
        # With account_reports installed it opens the General Ledger (ir.actions.client);
        # without it, the journal items view filtered by account and date.
        if action.get("res_model") == "account.move.line":
            self.assertIn(("account_id", "=", self.account.id), action["domain"])
            self.assertIn(("date", "<=", "2026-07-31"), action["domain"])
        else:
            # The account_reports client action breaks if the action loses its report_id:
            # the context is merged into, not replaced.
            gl_report = self.env.ref("account_reports.general_ledger_report")
            self.assertEqual(action["context"]["report_id"], gl_report.id)
            self.assertEqual(action["context"]["default_filter_accounts"], self.account.code)
            self.assertEqual(action["params"]["options"]["date"]["date_to"], "2026-07-31")

    # -- Three-dots menu: only when there is something to show -----------------
    def _drilldown_types_by_account(self):
        lines = self.report.get_report_values()["data"]["stock_variation"]["lines"]
        return {line["account_id"]: line["drilldown_types"] for line in lines}

    def test_counterpart_line_has_no_drilldown(self):
        """The counterpart account shows up in the Variation because the entry has two
        legs, but it has no detail of its own to open: nothing to show, no menu."""
        types_by_account = self._drilldown_types_by_account()
        self.assertIn(self.account_stock_variation.id, types_by_account, "The counterpart has a line")
        self.assertEqual(types_by_account[self.account_stock_variation.id], [])
        # The valuation account does have detail: at least this setUp's pending moves. The
        # absence of value adjustments is not asserted: the account is the company one and
        # may carry adjustments of other products.
        self.assertIn("stock_move", types_by_account[self.account.id])

    def test_valuation_line_offers_both_origins_when_both_exist(self):
        self.product_standard.standard_price = 13.0
        self.assertEqual(
            self._drilldown_types_by_account()[self.account.id],
            ["stock_move", "product_value"],
        )

    def test_no_drilldown_once_everything_is_booked(self):
        """Once the difference is booked there is no pending detail left and the menu goes
        away."""
        self._close()
        types_by_account = self._drilldown_types_by_account()
        self.assertFalse(types_by_account.get(self.account.id))

    # -- Edge cases ------------------------------------------------------------
    def test_drilldown_without_matching_products(self):
        """An account with no products booked to it cannot return everything: the action
        has to come back empty."""
        empty_account = self.env["account.account"].create(
            {"name": "Empty Valuation", "code": "110198", "account_type": "asset_current"}
        )
        action = self.report.action_open_variation_stock_moves(empty_account.id)
        self.assertFalse(self._records(action))
        action = self.report.action_open_variation_product_values(empty_account.id)
        self.assertFalse(self._records(action))
