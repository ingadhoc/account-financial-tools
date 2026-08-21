from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClosingEntryTraceability(TestStockValuationCommon):
    """Reading a global valuation entry: which moves it booked, and which line is whose.

    Both come from the functional testing of task 64440. Three periodic products sharing
    the valuation account, so a single closing produces several lines on that account.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move_standard = self._make_in_move(self.product_standard, 10, 10)  # value 100
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)  # value 100
        self.move_fifo = self._make_in_move(self.product_fifo, 2, 10)  # value 20
        # ``_make_in_move`` values through ``value_manual``, which records a
        # ``product.value``. A real receipt carries no manual adjustment, so they are
        # cleaned up to start from plain, non-revalued moves.
        self.env["product.value"].search(
            [("move_id", "in", (self.move_standard + self.move_avco + self.move_fifo).ids)]
        ).unlink()

    def _valuation_lines(self, entry):
        return entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)

    # -- The entry is reachable from every move it booked ----------------------
    def test_full_closing_links_moves_a_partial_closing_left_pending(self):
        """A move an earlier partial closing left out has to end up linked to the later
        full closing, whatever its date.

        The closing books the CUMULATIVE difference (inventory value minus booked value)
        with no lower date bound, so an old unbooked move IS in the entry. Bounding the
        linking by the previous closing date booked its value and left the move pointing
        at no entry, which is what the functional testing reported: the global entry did
        not show up on the move.
        """
        self.move_avco.date = fields.Datetime.now() - relativedelta(days=30)
        # Partial closing of another product: the avco move stays pending.
        self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        self.assertFalse(self.move_avco.account_move_id, "The partial closing did not book it")

        entry = self._close()
        self.assertEqual(self.move_avco.account_move_id, entry, "The full closing books it, so it links it")
        self.assertEqual(self.move_avco.related_account_move_id, entry)
        self.assertEqual(self.move_fifo.account_move_id, entry)
        # And nothing is left pending, which is the other half of the same statement: the
        # entry did book what those moves contributed.
        self.assertAlmostEqual(self.report.get_report_values()["data"]["stock_variation"]["value"], 0.0)

    def test_full_closing_links_moves_a_line_type_closing_left_pending(self):
        """Same thing after a closing filtered by Movement Type: the value adjustments
        entry books no move, so the later full closing is the one that links them."""
        self.move_avco.date = fields.Datetime.now() - relativedelta(days=30)
        self.product_standard.standard_price = 13.0  # a value adjustment to close on its own
        self.company.action_close_stock_valuation(auto_post=True, line_types=["product_value"])
        self.assertFalse(self.move_avco.account_move_id, "That closing booked no move")

        entry = self._close()
        self.assertEqual(self.move_avco.account_move_id, entry)
        self.assertEqual(self.move_standard.account_move_id, entry)

    def test_already_booked_moves_keep_their_entry(self):
        """No regression: a later closing must not re-point a move already booked by a
        posted one."""
        first = self._close()
        self.assertEqual(self.move_avco.account_move_id, first)
        self.product_standard.standard_price = 13.0
        second = self._close()
        self.assertNotEqual(second, first)
        self.assertEqual(self.move_avco.account_move_id, first, "Its original entry is untouched")

    # -- Which line belongs to which product ----------------------------------
    def test_valuation_lines_name_the_product(self):
        """The valuation account is the category's, so a global entry has several lines on
        it. The label names the product so the user can tell them apart."""
        entry = self._close()
        valuation_lines = self._valuation_lines(entry)
        self.assertGreater(len(valuation_lines), 1, "The products share the valuation account")
        for line in valuation_lines.filtered("product_id"):
            self.assertIn(line.product_id.display_name, line.name)
        # Every product is named on its own line, and the amounts are untouched.
        self.assertEqual(
            valuation_lines.product_id,
            self.product_standard + self.product_avco + self.product_fifo,
        )
        net = sum(valuation_lines.mapped("debit")) - sum(valuation_lines.mapped("credit"))
        self.assertAlmostEqual(net, 220.0)

    def test_counterpart_line_keeps_the_generic_label(self):
        """The counterpart is not attributed to any product, so naming one on it would be
        wrong."""
        entry = self._close()
        counterpart_lines = entry.line_ids - self._valuation_lines(entry)
        self.assertTrue(counterpart_lines)
        for line in counterpart_lines:
            for product in (self.product_standard, self.product_avco, self.product_fifo):
                self.assertNotIn(product.display_name, line.name)

    def test_manual_valuation_lines_name_the_product(self):
        """The manual valuation of moves builds the same kind of global entry, so it names
        the product on the valuation lines too."""
        wizard = (
            self.env["stock.move.valuation"]
            .with_context(default_move_ids=(self.move_avco + self.move_fifo).ids)
            .create({})
        )
        wizard.action_post()
        entry = self.move_avco.account_move_id
        valuation_lines = self._valuation_lines(entry)
        self.assertEqual(valuation_lines.product_id, self.product_avco + self.product_fifo)
        for line in valuation_lines:
            self.assertIn(line.product_id.display_name, line.name)
        counterpart_lines = entry.line_ids - valuation_lines
        for line in counterpart_lines:
            self.assertNotIn(self.product_avco.display_name, line.name)

    # -- Only a POSTED entry counts as the move's entry -------------------------
    def test_unposted_closing_is_not_shown_on_the_move(self):
        """A closing sent back to draft or cancelled booked nothing, so the move must not
        show it as its journal entry. The stored ``account_move_id`` keeps the reference,
        so posting it again brings the link back (functional feedback, task 64440)."""
        entry = self._close()
        self.assertEqual(self.move_avco.related_account_move_id, entry)

        entry.button_draft()
        self.assertEqual(self.move_avco.account_move_id, entry, "The stored reference is untouched")
        self.assertFalse(self.move_avco.related_account_move_id, "A draft entry values nothing")

        entry.button_cancel()
        self.assertFalse(self.move_avco.related_account_move_id)

        entry.button_draft()
        entry.action_post()
        self.assertEqual(self.move_avco.related_account_move_id, entry)

    def test_unposted_revaluation_entry_is_not_shown_on_the_move(self):
        """Same for the entry that booked a value adjustment, the one that wins over the
        move's own."""
        adjustment = self.env["product.value"].create(
            {"move_id": self.move_avco.id, "value": self.move_avco.value + 30.0}
        )
        entry = self._close()
        self.assertEqual(adjustment.account_move_id, entry)
        self.assertEqual(self.move_avco.related_account_move_id, entry)

        entry.button_draft()
        self.assertFalse(self.move_avco.related_account_move_id)

    # -- An adjustment with no variation is not marked as booked ---------------
    def test_closing_skips_adjustments_with_no_variation(self):
        """An adjustment that left the value where it was puts nothing in the entry, so it
        must not come out marked as booked: "no entry yet" is what identifies the
        difference still to adjust (functional feedback, task 64440)."""
        unchanged = self.env["product.value"].create({"move_id": self.move_fifo.id, "value": self.move_fifo.value})
        self.product_standard.standard_price = 13.0
        changed = self.env["product.value"].search(
            [("product_id", "=", self.product_standard.id)], order="id desc", limit=1
        )
        self.assertAlmostEqual(unchanged.delta, 0.0)
        self.assertNotAlmostEqual(changed.delta, 0.0)

        entry = self._close()

        self.assertEqual(changed.account_move_id, entry)
        self.assertFalse(unchanged.account_move_id, "Nothing to book, nothing to mark")
