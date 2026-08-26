from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestValuationReportFilters(TestStockValuationCommon):
    """Filters of the Inventory Valuation report. Data is created with .create() and the
    common helpers, no demo data. Every product used is periodic, so the moves stay
    unaccounted (``related_account_move_id = False``) until the closing, which is what the
    Movement Type filter needs."""

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        # Receipts (periodic). The move value is unit_cost * qty.
        # Watch out with the standard cost product: it is received AT ITS STANDARD COST
        # (10). Receiving it at another price and then deleting the ``product.value`` the
        # helper creates would leave a ``value`` the standard cost cannot produce in a real
        # flow (a normal receipt is valued at the standard, not at what was paid), and the
        # test would be measuring an unreachable state.
        self.move_standard = self._make_in_move(self.product_standard, 10, 10)  # value 100
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)  # value 100
        self.move_fifo = self._make_in_move(self.product_fifo, 2, 10)  # value 20
        self.valued_products = self.product_standard + self.product_avco + self.product_fifo
        # _make_in_move uses value_manual, which creates a product.value per move. In real
        # use a normal receipt carries no manual revaluation, so they are cleaned up for the
        # Movement Type filter to treat them as pure stock moves and not as Product Value.
        self.env["product.value"].search(
            [("move_id", "in", (self.move_standard + self.move_avco + self.move_fifo).ids)]
        ).unlink()

    def _data(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]

    # -- Regression ------------------------------------------------------------
    def test_no_filters_matches_filter_all(self):
        """Filtering by every valued product must equal not filtering. Catches the filtered
        path drifting away from the standard it copies."""
        base = self._data()
        allp = self._data(product_ids=self.valued_products.ids)
        for section in ("initial_balance", "ending_stock", "stock_variation"):
            self.assertAlmostEqual(
                base[section]["value"],
                allp[section]["value"],
                msg=f"Section {section} differs between no-filter and filter-all",
            )

    # -- The product filters scope the three sections --------------------------
    def test_filter_by_category_scopes_ending_stock(self):
        data = self._data(categ_ids=[self.category_standard.id])
        expected = self.product_standard.with_company(self.company).total_value
        self.assertAlmostEqual(data["ending_stock"]["value"], expected)
        # It has to be a subset of the total.
        full = self._data()["ending_stock"]["value"]
        self.assertLess(data["ending_stock"]["value"], full)

    def test_filter_by_cost_method(self):
        data = self._data(cost_methods=["average"])
        expected = self.product_avco.with_company(self.company).total_value
        self.assertAlmostEqual(data["ending_stock"]["value"], expected)

    def test_filter_by_valuation_type(self):
        # Every product with stock is periodic, so real_time gives 0.
        data_rt = self._data(valuations=["real_time"])
        self.assertAlmostEqual(data_rt["ending_stock"]["value"], 0.0)
        # periodic equals the total, as there is no real_time product with stock.
        data_periodic = self._data(valuations=["periodic"])
        self.assertAlmostEqual(data_periodic["ending_stock"]["value"], self._data()["ending_stock"]["value"])

    def test_filters_combine_and(self):
        # Standard category AND average method is an empty set, hence 0.
        data = self._data(categ_ids=[self.category_standard.id], cost_methods=["average"])
        self.assertAlmostEqual(data["ending_stock"]["value"], 0.0)

    # -- The Movement Type filter only affects the Variation -------------------
    def test_line_type_stock_move_vs_product_value(self):
        # A REAL revaluation of the avco move: what makes it one is the DELTA, so an
        # adjustment recording the same value would change nothing and would leave the move
        # in Stock Moves (see ``test_revaluation_criterion``).
        self.env["product.value"].create(
            {
                "move_id": self.move_avco.id,
                "value": self.move_avco.value + 50.0,
            }
        )
        native = self._data()["stock_variation"]["value"]
        # Stock Moves: standard (100) + fifo (20). The revalued avco move is out whatever
        # its new value is.
        vsm = self._data(line_types=["stock_move"])["stock_variation"]["value"]
        self.assertAlmostEqual(vsm, 120.0)
        # Product Value takes what the revalued move contributes, as the remainder.
        vpv = self._data(line_types=["product_value"])["stock_variation"]["value"]
        self.assertNotAlmostEqual(vpv, 0.0)
        # The two components add up to the native variation, with no spurious remainder.
        self.assertAlmostEqual(vsm + vpv, native)

    def test_line_type_without_adjustments_is_all_stock_moves(self):
        """With no ``product.value`` at all, everything a product contributes has to fall
        into Stock Moves and nothing into Product Value: the move's ``value`` already is the
        criterion the inventory is valued with."""
        scope = {"categ_ids": [self.category_standard.id]}
        self.assertAlmostEqual(self.move_standard.value, 100.0)
        self.assertAlmostEqual(self.product_standard.with_company(self.company).total_value, 100.0)
        vpv = self._data(line_types=["product_value"], **scope)["stock_variation"]["value"]
        self.assertAlmostEqual(vpv, 0.0)
        vsm = self._data(line_types=["stock_move"], **scope)["stock_variation"]["value"]
        self.assertAlmostEqual(vsm, 100.0)

    def test_line_type_move_adjustment_goes_to_product_value(self):
        """A move with a manual adjustment is left OUT of Stock Moves and what it
        contributes goes to the adjustments component.

        The amount stays 100 and not 150: under standard cost the inventory is worth
        quantity × standard cost, so adjusting a move's ``value`` does not move the product
        valuation, as it would under AVCO/FIFO. What changes is which component it hangs
        from."""
        scope = {"categ_ids": [self.category_standard.id]}
        self.env["product.value"].create({"move_id": self.move_standard.id, "value": 150.0})
        self.assertAlmostEqual(self.product_standard.with_company(self.company).total_value, 100.0)
        vsm = self._data(line_types=["stock_move"], **scope)["stock_variation"]["value"]
        self.assertAlmostEqual(vsm, 0.0, msg="The revalued move leaves the stock component")
        vpv = self._data(line_types=["product_value"], **scope)["stock_variation"]["value"]
        self.assertAlmostEqual(vpv, 100.0, msg="The adjustments component takes its contribution")

    def test_line_type_does_not_touch_the_initial_balance(self):
        """The Initial Balance is the already booked starting point, a balance with no
        origin, so the per-origin filter does not touch it."""
        self.assertAlmostEqual(
            self._data()["initial_balance"]["value"],
            self._data(line_types=["stock_move"])["initial_balance"]["value"],
        )

    def test_line_type_projects_the_ending_stock(self):
        """With the filter on, the report has to add up: Ending Stock is projected as
        Initial Balance + filtered variation, i.e. the booked value the stock would have if
        only that portion were booked, which is what the entry generated with the filter
        books."""
        for line_types in (["stock_move"], ["product_value"]):
            data = self._data(line_types=line_types)
            self.assertAlmostEqual(
                data["ending_stock"]["value"],
                data["initial_balance"]["value"] + data["stock_variation"]["value"],
                msg=f"The report does not add up with line_types={line_types}",
            )

    def test_ending_stock_without_line_types_is_the_real_state(self):
        """With no filter, Ending Stock is still the real state of the stock and not a
        projection."""
        expected = sum(self.valued_products.mapped(lambda p: p.with_company(self.company).total_value))
        self.assertAlmostEqual(self._data()["ending_stock"]["value"], expected)

    def test_both_line_types_projections_add_up_to_the_real_state(self):
        """The two projections are complementary: starting from the same Initial Balance,
        the two filtered variations add up to the whole variation, so together they project
        the real state."""
        initial = self._data()["initial_balance"]["value"]
        projected_moves = self._data(line_types=["stock_move"])["ending_stock"]["value"]
        projected_values = self._data(line_types=["product_value"])["ending_stock"]["value"]
        self.assertAlmostEqual(
            (projected_moves - initial) + (projected_values - initial),
            self._data()["ending_stock"]["value"] - initial,
        )

    def test_line_type_both_normalizes_to_no_filter(self):
        # Selecting both types means no Movement Type filter: it uses the native variation
        # computation, not the breakdown per origin.
        both = self._data(line_types=["stock_move", "product_value"])
        base = self._data()
        self.assertAlmostEqual(both["stock_variation"]["value"], base["stock_variation"]["value"])

    # -- Initial Balance scoped to the filter ----------------------------------
    def _book(self, moves):
        """Book those moves with the manual valuation wizard, which leaves the lines
        attributed to their product."""
        self.env["stock.move.valuation"].with_context(default_move_ids=moves.ids).create({}).action_post()

    def test_initial_balance_scoped_by_product_filter(self):
        """The three products share the company valuation account, so without per-product
        attribution the filtered Initial Balance used to show the whole account balance."""
        self._book(self.move_avco)  # 100, con product_id
        self.assertAlmostEqual(self._data()["initial_balance"]["value"], 100.0, msg="With no filter, the whole account")
        self.assertAlmostEqual(
            self._data(product_ids=self.product_avco.ids)["initial_balance"]["value"],
            100.0,
            msg="Filtered by the booked product, its own balance",
        )
        self.assertAlmostEqual(
            self._data(product_ids=self.product_standard.ids)["initial_balance"]["value"],
            0.0,
            msg="Filtered by another product of the same account, nothing",
        )

    def test_filtered_report_adds_up(self):
        """With the Initial Balance scoped, the report adds up: initial + variation = ending."""
        self._book(self.move_avco)
        for scope in ({}, {"product_ids": self.product_avco.ids}, {"product_ids": self.product_standard.ids}):
            data = self._data(**scope)
            self.assertAlmostEqual(
                data["initial_balance"]["value"] + data["stock_variation"]["value"],
                data["ending_stock"]["value"],
                msg=f"The report does not add up with {scope}",
            )

    def test_closing_attributes_the_balance_by_product(self):
        """The closing splits the valuation account per product, same amount and same
        counterpart, which is why afterwards the filtered Initial Balance gives that
        product's balance and the real pending amount."""
        self._close()
        data = self._data()
        self.assertAlmostEqual(data["initial_balance"]["value"], 220.0, msg="100 + 100 + 20")
        self.assertAlmostEqual(data["stock_variation"]["value"], 0.0, msg="Everything is booked already")
        valuation_lines = self.env["account.move.line"].search(
            [("account_id", "=", self.account_stock_valuation.id), ("parent_state", "=", "posted")]
        )
        self.assertFalse(
            valuation_lines.filtered(lambda line: not line.product_id),
            "No closing line is left unattributed",
        )
        avco = self._data(product_ids=self.product_avco.ids)
        self.assertAlmostEqual(avco["initial_balance"]["value"], 100.0, msg="The balance attributed to the product")
        self.assertAlmostEqual(avco["stock_variation"]["value"], 0.0, msg="Nothing pending for that product")

    def test_closing_keeps_working_with_a_product_filter_after_closing(self):
        """A move created after the closing is the only pending one, and the product filter
        isolates it."""
        self._close()
        self._make_in_move(self.product_fifo, 1, 30)  # +30 pending
        fifo = self._data(product_ids=self.product_fifo.ids)
        self.assertAlmostEqual(fifo["initial_balance"]["value"], 20.0)
        self.assertAlmostEqual(fifo["stock_variation"]["value"], 30.0)
        self.assertAlmostEqual(fifo["ending_stock"]["value"], 50.0)
        avco = self._data(product_ids=self.product_avco.ids)
        self.assertAlmostEqual(avco["stock_variation"]["value"], 0.0, msg="The other product has nothing pending")

    def test_partial_closing_books_only_the_filtered_product(self):
        """The entry generated with a product filter has to book exactly the variation the
        report shows for that product.

        The three products share the valuation account, so taking the whole account
        balance as the starting point dragged in the balance already booked for the OTHER
        products and the entry came out with the wrong sign and amount.
        """
        self._close()  # 220 booked, attributed per product
        self.product_standard.standard_price = 13.0  # 10 units: 100 -> 130, so 30 pending
        data = self._data(product_ids=self.product_standard.ids)
        self.assertAlmostEqual(data["initial_balance"]["value"], 100.0)
        self.assertAlmostEqual(data["stock_variation"]["value"], 30.0)

        action = self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        entry = self.env["account.move"].browse(action["res_id"])
        valuation_lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        net = sum(valuation_lines.mapped("debit")) - sum(valuation_lines.mapped("credit"))
        self.assertAlmostEqual(net, 30.0, msg="The entry books the variation of the filtered product only")
        self.assertEqual(valuation_lines.product_id, self.product_standard, "Attributed to the filtered product")
        # And the report is left square for that product, without touching the others.
        after = self._data(product_ids=self.product_standard.ids)
        self.assertAlmostEqual(after["initial_balance"]["value"], 130.0)
        self.assertAlmostEqual(after["stock_variation"]["value"], 0.0)
        avco = self._data(product_ids=self.product_avco.ids)
        self.assertAlmostEqual(avco["initial_balance"]["value"], 100.0, msg="The other product was not touched")
        self.assertAlmostEqual(avco["stock_variation"]["value"], 0.0)

    def test_partial_closing_by_line_type_books_only_the_filtered_product(self):
        """Same thing with the Movement Type filter on top: the remainder component reads
        the booked value of the filtered products, not the whole account balance."""
        self._close()
        self.product_standard.standard_price = 13.0
        action = self.company.action_close_stock_valuation(
            auto_post=True,
            product_ids=self.product_standard.ids,
            line_types=["product_value"],
        )
        entry = self.env["account.move"].browse(action["res_id"])
        valuation_lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        net = sum(valuation_lines.mapped("debit")) - sum(valuation_lines.mapped("credit"))
        self.assertAlmostEqual(net, 30.0)

    def test_line_type_filter_keeps_the_whole_account_balance(self):
        """The per-origin filter scopes no product: the Initial Balance is still the
        account's, the portion with no product included."""
        self._book(self.move_avco)
        self.assertAlmostEqual(
            self._data(line_types=["stock_move"])["initial_balance"]["value"],
            self._data()["initial_balance"]["value"],
        )

    def test_line_type_scoped_by_product_filter(self):
        # The Movement Type filter honours the product ones too: fifo + stock_move leaves
        # only the fifo move (20).
        data = self._data(categ_ids=[self.category_fifo.id], line_types=["stock_move"])
        self.assertAlmostEqual(data["stock_variation"]["value"], 20.0)
