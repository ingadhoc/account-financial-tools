from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestValuationRevaluationEntry(TestStockValuationCommon):
    """When the inventory variation comes from a ``product.value`` change (a cost change
    on the product or a manual adjustment of a move's value), the entry the valuation
    closing generates has to be reachable.

    Out of the box it was nowhere: ``product.value`` keeps no reference to the entry, and
    the revalued ``stock.move`` still points at its original one in ``account_move_id``,
    a Many2one already taken.
    """

    def setUp(self):
        super().setUp()
        # Periodic receipts: they stay unaccounted until the closing.
        self.move_standard = self._make_in_move(self.product_standard, 10, 10)  # value 100
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)  # value 100
        # ``_make_in_move`` values through ``value_manual``, which creates a
        # ``product.value`` per move. A real receipt carries no manual adjustment, so they
        # are cleaned up to start from non-revalued moves.
        self.env["product.value"].search([("move_id", "in", (self.move_standard + self.move_avco).ids)]).unlink()

    def _last_product_value(self, domain):
        return self.env["product.value"].search(domain, order="id desc", limit=1)

    # -- Cost change on the product (product.value with no move) ---------------
    def test_standard_price_change_links_closing_entry(self):
        first_closing = self._close()
        self.assertTrue(first_closing, "The first closing should generate an entry")

        self.product_standard.standard_price = 13.0
        price_change = self._last_product_value(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)]
        )
        self.assertTrue(price_change, "The price change should record a product.value")
        self.assertFalse(price_change.account_move_id, "Not booked yet")

        second_closing = self._close()
        self.assertNotEqual(second_closing, first_closing)
        self.assertEqual(
            price_change.account_move_id,
            second_closing,
            "The value adjustment has to be linked to the closing that booked it",
        )
        # The move original entry is not overwritten.
        self.assertEqual(self.move_standard.account_move_id, first_closing)
        # The price change hangs from no move, so the move's related entry is still the
        # one of its original valuation.
        self.assertEqual(self.move_standard.related_account_move_id, first_closing)

    # -- Manual adjustment of a move value (product.value with a move) ---------
    def test_move_value_adjustment_links_closing_entry_and_move(self):
        first_closing = self._close()

        self.move_avco.value_manual = 130.0
        adjustment = self._last_product_value([("move_id", "=", self.move_avco.id)])
        self.assertTrue(adjustment)
        self.assertFalse(adjustment.account_move_id)

        second_closing = self._close()
        self.assertNotEqual(second_closing, first_closing)
        self.assertEqual(adjustment.account_move_id, second_closing)
        self.assertEqual(
            self.move_avco.related_account_move_id,
            second_closing,
            "The cost change entry has to be reflected on the move",
        )
        # Without overwriting the standard entry of the original valuation.
        self.assertEqual(self.move_avco.account_move_id, first_closing)

    def test_related_entry_takes_the_last_booked_adjustment(self):
        self._close()
        self.move_avco.value_manual = 130.0
        closing_2 = self._close()
        self.assertEqual(self.move_avco.related_account_move_id, closing_2)
        self.move_avco.value_manual = 150.0
        closing_3 = self._close()
        self.assertEqual(self.move_avco.related_account_move_id, closing_3)

    def test_unbooked_adjustment_does_not_change_the_related_entry(self):
        """While the adjustment is not booked, the related entry is still the original
        valuation one: there is no revaluation entry to show yet."""
        first_closing = self._close()
        self.move_avco.value_manual = 130.0
        self.assertEqual(self.move_avco.related_account_move_id, first_closing)

    # -- Delta ---------------------------------------------------------------
    def test_delta_of_move_adjustment(self):
        # With no previous adjustment the base is the value the system had computed for
        # the move (10 units at 10 = 100).
        self.move_standard.value_manual = 150.0
        first = self._last_product_value([("move_id", "=", self.move_standard.id)])
        self.assertAlmostEqual(first.delta, 50.0)
        # With a previous adjustment the base is that adjustment value.
        self.move_standard.value_manual = 170.0
        second = self._last_product_value([("move_id", "=", self.move_standard.id)])
        self.assertNotEqual(second, first)
        self.assertAlmostEqual(second.delta, 20.0)

    def test_delta_of_move_adjustment_on_avco(self):
        """Under AVCO/FIFO the move adjustment drags the product's ``standard_price``
        along, so the previous value cannot be recomputed afterwards: it is captured when
        the adjustment is recorded."""
        self.move_avco.value_manual = 130.0
        adjustment = self._last_product_value([("move_id", "=", self.move_avco.id)])
        self.assertAlmostEqual(adjustment.previous_value, 100.0)
        self.assertAlmostEqual(adjustment.delta, 30.0)

    def test_delta_of_price_change(self):
        # Creating the product already left a product.value with the initial price (10),
        # so the delta of the change to 13 is a unit one: 3.
        self.product_standard.standard_price = 13.0
        price_change = self._last_product_value(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)]
        )
        self.assertAlmostEqual(price_change.delta, 3.0)

    # -- Search ----------------------------------------------------------------
    def test_search_related_entry_covers_the_revaluation(self):
        first_closing = self._close()
        self.move_avco.value_manual = 130.0
        revaluation_closing = self._close()

        Move = self.env["stock.move"]
        # The search has to follow the field: the revalued move is found by its
        # revaluation entry, and no longer by the original one.
        by_revaluation = Move.search([("related_account_move_id", "=", revaluation_closing.id)])
        self.assertIn(self.move_avco, by_revaluation)
        self.assertNotIn(self.move_standard, by_revaluation)

        by_original = Move.search([("related_account_move_id", "=", first_closing.id)])
        self.assertIn(self.move_standard, by_original)
        self.assertNotIn(self.move_avco, by_original)

        with_entry = Move.search([("related_account_move_id", "!=", False)])
        self.assertIn(self.move_avco, with_entry)
        self.assertIn(self.move_standard, with_entry)

    def test_search_moves_with_unbooked_adjustment(self):
        """The "Revaluation Not Booked" filter of the search view."""
        self._close()
        self.move_avco.value_manual = 130.0
        domain = [("product_value_ids", "any", [("account_move_id", "=", False)])]
        pending = self.env["stock.move"].search(domain)
        self.assertIn(self.move_avco, pending)
        self.assertNotIn(self.move_standard, pending)
        self._close()
        self.assertNotIn(self.move_avco, self.env["stock.move"].search(domain))

    # -- Cierre parcial (Mejora 1 + Mejora 4) --------------------------------
    def test_partial_closing_only_links_filtered_products(self):
        self._close()
        self.product_standard.standard_price = 13.0
        self.move_avco.value_manual = 130.0
        price_change = self._last_product_value(
            [("product_id", "=", self.product_standard.id), ("move_id", "=", False)]
        )
        adjustment = self._last_product_value([("move_id", "=", self.move_avco.id)])

        action = self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        partial_closing = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(price_change.account_move_id, partial_closing)
        self.assertFalse(
            adjustment.account_move_id,
            "Un cierre parcial no debe marcar como contabilizados los ajustes de otros productos",
        )
