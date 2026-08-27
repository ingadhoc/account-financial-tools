from odoo import Command, fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestManualMoveValuation(TestStockValuationCommon):
    """Manual booking of selected stock moves: the draft entry grouped by the accounts of
    the product categories, and no way to value the same move twice."""

    def setUp(self):
        super().setUp()
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)  # value 100
        self.move_fifo = self._make_in_move(self.product_fifo, 2, 10)  # value 20
        self.env["product.value"].search([("move_id", "in", (self.move_avco + self.move_fifo).ids)]).unlink()

    def _wizard(self, moves):
        return self.env["stock.move.valuation"].with_context(default_move_ids=moves.ids).create({})

    # -- Draft entry -----------------------------------------------------------
    def test_draft_groups_by_account_and_product(self):
        """The accounts are still the categories' ones (here both products share the
        valuation account), but every line is attributed to its product, which is what later
        lets the report's Initial Balance be filtered by product. The total does not change:
        120 (100 + 20)."""
        wizard = self._wizard(self.move_avco + self.move_fifo)
        self.assertEqual(wizard.move_ids, self.move_avco + self.move_fifo)
        self.assertAlmostEqual(wizard.total, 120.0)
        debit_lines = wizard.line_ids.filtered("debit")
        self.assertEqual(debit_lines.account_id, self.account_stock_valuation, "A single valuation account")
        self.assertEqual(debit_lines.product_id, self.product_avco + self.product_fifo, "One line per product")
        self.assertAlmostEqual(sum(debit_lines.mapped("debit")), 120.0)
        avco_line = debit_lines.filtered(lambda line: line.product_id == self.product_avco)
        self.assertAlmostEqual(avco_line.debit, 100.0)

    def test_posted_entry_carries_the_product(self):
        """The booked line carries the product: that is the attribution the filtered Initial
        Balance needs."""
        wizard = self._wizard(self.move_avco)
        wizard.action_post()
        entry_lines = self.move_avco.account_move_id.line_ids
        self.assertEqual(entry_lines.filtered("debit").product_id, self.product_avco)

    def test_draft_defaults(self):
        wizard = self._wizard(self.move_avco)
        self.assertEqual(wizard.journal_id, self.company.account_stock_journal_id)
        # Same source the default reads: asserting against ``cr.now()`` compared the user's
        # timezone with a UTC clock, one day apart inside the offset window (ticket 126535).
        self.assertEqual(wizard.date, fields.Date.context_today(wizard))

    def test_outgoing_move_subtracts(self):
        out_move = self._make_out_move(self.product_avco, 1)
        self.env["product.value"].search([("move_id", "=", out_move.id)]).unlink()
        wizard = self._wizard(out_move)
        # An outgoing move of 1 unit at a cost of 25 subtracts from the asset, so the
        # valuation account is credited.
        credit_line = wizard.line_ids.filtered("credit")
        self.assertEqual(credit_line.account_id, self.account_stock_valuation)
        self.assertAlmostEqual(credit_line.credit, 25.0)

    def test_standard_cost_uses_inventory_criterion(self):
        """Same criterion as the Movement Type filter: the move's ``value``, which under
        standard cost already is quantity × standard cost, since a normal receipt is valued
        at the standard and not at what was paid."""
        move_standard = self._make_in_move(self.product_standard, 10, 10)
        self.env["product.value"].search([("move_id", "=", move_standard.id)]).unlink()
        wizard = self._wizard(move_standard)
        self.assertAlmostEqual(move_standard.value, 100.0)
        self.assertAlmostEqual(
            wizard.total,
            self.product_standard.with_company(self.company).total_value,
            msg="The draft books the same as the inventory is worth",
        )

    # -- Posting ---------------------------------------------------------------
    def test_post_creates_entry_and_links_moves(self):
        moves = self.move_avco + self.move_fifo
        wizard = self._wizard(moves)
        action = wizard.action_post()
        entry = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(entry.state, "posted")
        self.assertEqual(entry.journal_id, wizard.journal_id)
        self.assertEqual(entry.date, wizard.date)
        self.assertAlmostEqual(sum(entry.line_ids.mapped("debit")), 120.0)
        for move in moves:
            self.assertEqual(move.account_move_id, entry)
            self.assertEqual(move.related_account_move_id, entry)

    def test_posted_moves_leave_the_pending_variation(self):
        """Once valued, the moves are no longer part of the pending variation the report
        shows."""
        report = self.env["stock_account.stock.valuation.report"]
        before = report.get_report_values(line_types=["stock_move"])["data"]["stock_variation"]["value"]
        self.assertAlmostEqual(before, 120.0)
        self._wizard(self.move_avco + self.move_fifo).action_post()
        after = report.get_report_values(line_types=["stock_move"])["data"]["stock_variation"]["value"]
        self.assertAlmostEqual(after, 0.0)

    # -- No double valuation ---------------------------------------------------
    def test_already_valued_moves_are_excluded_with_warning(self):
        self._wizard(self.move_avco).action_post()
        wizard = self._wizard(self.move_avco + self.move_fifo)
        self.assertEqual(wizard.move_ids, self.move_fifo, "The already valued one is left out")
        self.assertTrue(wizard.excluded_warning)
        self.assertIn(self.move_avco.reference, wizard.excluded_warning)
        self.assertAlmostEqual(wizard.total, 20.0)

    def test_excluded_warning_with_moves_without_reference(self):
        """Moves with no picking have an empty ``reference``: the warning must not break
        because of it."""
        move = self.env["stock.move"].create(
            {
                "product_id": self.product_avco.id,
                "product_uom_qty": 1,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "company_id": self.company.id,
            }
        )
        move._action_confirm()
        move.quantity = 1
        move.picked = True
        move._action_done()
        self.assertFalse(move.reference)
        self._wizard(move).action_post()
        wizard = self._wizard(move + self.move_fifo)
        self.assertEqual(wizard.move_ids, self.move_fifo)
        self.assertTrue(wizard.excluded_warning)

    def test_all_moves_already_valued_raises(self):
        self._wizard(self.move_avco).action_post()
        with self.assertRaises(UserError):
            self._wizard(self.move_avco)

    def test_posting_twice_does_not_duplicate(self):
        first = self.env["account.move"].browse(self._wizard(self.move_avco).action_post()["res_id"])
        with self.assertRaises(UserError):
            self._wizard(self.move_avco)
        self.assertEqual(self.move_avco.account_move_id, first)
        entries = self.env["account.move"].search([("journal_id", "=", self.company.account_stock_journal_id.id)])
        self.assertEqual(entries, first, "There should be no second entry")

    # -- Action entry point ----------------------------------------------------
    def test_action_value_moves_opens_the_wizard(self):
        action = (self.move_avco + self.move_fifo).action_value_moves()
        self.assertEqual(action["res_model"], "stock.move.valuation")
        self.assertEqual(sorted(action["context"]["default_move_ids"]), sorted((self.move_avco + self.move_fifo).ids))

    def test_action_from_move_lines_resolves_moves(self):
        """Moves History lists ``stock.move.line``: the action has to resolve the moves of
        the selected lines, deduplicated."""
        lines = (self.move_avco + self.move_fifo).move_line_ids
        self.assertTrue(lines)
        action = lines.action_value_moves()
        self.assertEqual(action["res_model"], "stock.move.valuation")
        self.assertEqual(
            sorted(action["context"]["default_move_ids"]),
            sorted((self.move_avco + self.move_fifo).ids),
        )
        wizard = self.env["stock.move.valuation"].with_context(**action["context"]).create({})
        self.assertEqual(wizard.move_ids, self.move_avco + self.move_fifo)
        self.assertAlmostEqual(wizard.total, 120.0)
        self.assertFalse(wizard.partial_lines_warning, "Every line was selected")

    def test_action_from_partial_line_selection_warns(self):
        """Valuation goes by move: selecting only some lines still values the move whole,
        and that has to be warned about."""
        move = self.env["stock.move"].create(
            {
                "product_id": self.product_avco.id,
                "product_uom_qty": 6,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "company_id": self.company.id,
            }
        )
        move._action_confirm()
        move.move_line_ids.unlink()
        move.move_line_ids = [
            Command.create(
                {
                    "product_id": self.product_avco.id,
                    "location_id": self.supplier_location.id,
                    "location_dest_id": self.stock_location.id,
                    "quantity": 3,
                }
            )
            for _ in range(2)
        ]
        move.picked = True
        move._action_done()
        self.assertEqual(len(move.move_line_ids), 2)
        action = move.move_line_ids[0].action_value_moves()
        wizard = self.env["stock.move.valuation"].with_context(**action["context"]).create({})
        self.assertEqual(wizard.move_ids, move, "Se valoriza el movimiento completo")
        self.assertTrue(wizard.partial_lines_warning)

    def test_action_value_moves_requires_done_moves(self):
        draft_move = self.env["stock.move"].create(
            {
                "product_id": self.product_avco.id,
                "product_uom_qty": 1,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(UserError):
            draft_move.action_value_moves()
