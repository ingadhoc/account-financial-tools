from odoo.tests import tagged

from .common import TestStockValuationUXCommon


@tagged("post_install", "-at_install")
class TestRevaluationSplit(TestStockValuationUXCommon):
    """How a revaluation splits the pending variation between the Stock Moves and the
    Product Value components, per costing method.

    The total is always the same; what changes is which component takes it.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["account.stock.valuation.report"]

    def _receive(self, product, quantity, unit_cost):
        move = self._make_in_move(product, quantity, unit_cost)
        # ``_make_in_move`` values through ``value_manual``, which records a
        # ``product.value``. A real receipt carries no manual adjustment.
        self.env["product.value"].search([("move_id", "=", move.id)]).unlink()
        return move

    def _split(self):
        values = {}
        for line_type in ("stock_move", "product_value"):
            data = self.report.get_report_values(line_types=[line_type])["data"]
            values[line_type] = data["stock_variation"]["value"]
        return values["stock_move"], values["product_value"]

    def _assert_split(self, stock_move, product_value):
        self.assertEqual(
            tuple(round(value, 2) for value in self._split()),
            (stock_move, product_value),
            "(Stock Moves, Product Value)",
        )

    # -- Cost change on an open receipt -----------------------------------------
    def test_cost_change_open_receipt_standard(self):
        """The open move is revalued, so the change stays inside Stock Moves. In 19 it
        went to Product Value (100 / 30)."""
        self._receive(self.product_standard, 10, 10)
        self.product_standard.standard_price = 13.0
        self._assert_split(130.0, 0.0)

    def test_cost_change_open_receipt_avco(self):
        self._receive(self.product_avco, 10, 10)
        self.product_avco.standard_price = 13.0
        self._assert_split(130.0, 0.0)

    # -- Cost change with part of the stock already closed -----------------------
    def test_cost_change_closed_and_open_receipts_standard(self):
        """The change on the closed stock goes to Product Value (10 x 3); the one on the
        open receipt stays inside its move (5 x 13)."""
        self._receive(self.product_standard, 10, 10)
        self._close()
        self._receive(self.product_standard, 5, 10)
        self.product_standard.standard_price = 13.0
        self._assert_split(65.0, 30.0)

    def test_cost_change_closed_and_open_receipts_avco(self):
        self._receive(self.product_avco, 10, 10)
        self._close()
        self._receive(self.product_avco, 5, 10)
        self.product_avco.standard_price = 13.0
        self._assert_split(65.0, 30.0)

    # -- Manual adjustment of a move's value ------------------------------------
    def test_manual_adjustment_open_move_takes_its_whole_value(self):
        """The revalued move leaves Stock Moves, so Product Value takes its whole value,
        not only the difference."""
        move = self._receive(self.product_avco, 10, 10)
        self.env["product.value"].create({"move_id": move.id, "value": 130.0, "company_id": self.company.id})
        self._assert_split(0.0, 130.0)

    def test_manual_adjustment_closed_move_takes_the_difference(self):
        move = self._receive(self.product_avco, 10, 10)
        self._close()
        self.env["product.value"].create({"move_id": move.id, "value": 130.0, "company_id": self.company.id})
        self._assert_split(0.0, 30.0)
