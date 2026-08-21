from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRevaluationCriterion(TestStockValuationCommon):
    """Which value adjustments take a move OUT of the Stock Moves component of the
    variation. The criterion is the delta in company currency, not the mere existence of
    a ``product.value`` pointing at the move (task 64440, clarification Q2)."""

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move = self._make_in_move(self.product_avco, 4, 25)  # value 100
        # ``_make_in_move`` goes through ``value_manual``, which records a
        # ``product.value``. A normal receipt carries no adjustment, so it is cleaned up
        # and each test records the one it wants to measure.
        self.env["product.value"].search([("move_id", "=", self.move.id)]).unlink()

    def _revalued_ids(self):
        return self.report._get_revalued_move_ids(self.product_avco)

    def _adjust(self, value):
        return self.env["product.value"].create(
            {
                "move_id": self.move.id,
                "value": value,
                "company_id": self.company.id,
            }
        )

    def test_move_without_adjustment_is_not_revalued(self):
        self.assertNotIn(self.move.id, self._revalued_ids())

    def test_adjustment_changing_the_value_is_a_revaluation(self):
        self._adjust(self.move.value + 50)
        self.assertIn(self.move.id, self._revalued_ids())

    def test_adjustment_with_no_delta_is_not_a_revaluation(self):
        """An adjustment recording the SAME value moved nothing, so its move stays in the
        Stock Moves component.

        This is what lets a module record an adjustment on ANOTHER amount —a
        secondary-currency correction in ``stock_currency_valuation``, task 58212— without
        the whole value of the move silently migrating to the Product Value remainder. The
        report total would still add up, because that component is a residue, so the
        breakdown would be wrong without anything failing.
        """
        self._adjust(self.move.value)
        self.assertNotIn(self.move.id, self._revalued_ids())

    def test_adjustment_to_zero_is_a_revaluation(self):
        """Taking the value to zero is a big delta, not a zero delta."""
        self._adjust(0.0)
        self.assertIn(self.move.id, self._revalued_ids())
