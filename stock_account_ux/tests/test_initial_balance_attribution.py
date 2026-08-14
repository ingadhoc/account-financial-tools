from dateutil.relativedelta import relativedelta
from odoo import Command
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestInitialBalanceAttribution(TestStockValuationCommon):
    """Initial Balance of the report while a product filter is active, when part of the
    valuation account was booked with NO product.

    That portion is real —closings posted before this module aggregate per account with
    ``product_id = False``, and so do the location reclassifications and any manual entry
    on the account— and it used to be dropped from the filtered report. The filtered
    report then disagreed with the unfiltered one: product by product it reported more
    left to book than there actually was, and closing each product in turn would have
    booked that portion twice (task 64440, functional testing).

    Scenario: three periodic products sharing the valuation account, with inventory values
    of 100 / 100 / 20, plus 60 booked on the account with no product.
    """

    def setUp(self):
        super().setUp()
        self.report = self.env["stock_account.stock.valuation.report"]
        self.move_standard = self._make_in_move(self.product_standard, 10, 10)  # 100
        self.move_avco = self._make_in_move(self.product_avco, 4, 25)  # 100
        self.move_fifo = self._make_in_move(self.product_fifo, 2, 10)  # 20
        self.products = self.product_standard + self.product_avco + self.product_fifo
        # A real receipt carries no manual adjustment; the helper uses one to value.
        self.env["product.value"].search(
            [("move_id", "in", (self.move_standard + self.move_avco + self.move_fifo).ids)]
        ).unlink()

    def _book_without_product(self, amount=60.0, date=None):
        """Entry on the valuation account carrying no product, which is how the standard
        closing books and how an accountant posts by hand."""
        counterpart = self.account_stock_valuation.account_stock_variation_id or self.company.expense_account_id
        entry = self.env["account.move"].create(
            {
                "journal_id": self.company.account_stock_journal_id.id,
                "date": date or self.env.cr.now().date(),
                "ref": "Booked with no product",
                "company_id": self.company.id,
                "line_ids": [
                    Command.create({"account_id": self.account_stock_valuation.id, "debit": amount, "credit": 0.0}),
                    Command.create({"account_id": counterpart.id, "debit": 0.0, "credit": amount}),
                ],
            }
        )
        entry._post()
        return entry

    def _data(self, **kwargs):
        return self.report.get_report_values(**kwargs)["data"]

    def _initial(self, **kwargs):
        return self._data(**kwargs)["initial_balance"]["value"]

    def _variation(self, **kwargs):
        return self._data(**kwargs)["stock_variation"]["value"]

    # -- The invariant that was broken -----------------------------------------
    def test_filtering_by_every_product_matches_no_filter(self):
        """The whole point: with an unattributed portion around, filtering by every
        product has to equal not filtering. That is what stops the portion from being
        counted once per product."""
        self._book_without_product()
        base = self._data()
        allp = self._data(product_ids=self.products.ids)
        self.assertAlmostEqual(allp["initial_balance"]["value"], base["initial_balance"]["value"])
        self.assertAlmostEqual(allp["stock_variation"]["value"], base["stock_variation"]["value"])
        self.assertAlmostEqual(allp["ending_stock"]["value"], base["ending_stock"]["value"])

    def test_per_product_initial_balances_add_up_to_the_total(self):
        self._book_without_product()
        self.assertAlmostEqual(self._initial(), 60.0)
        self.assertAlmostEqual(sum(self._initial(product_ids=p.ids) for p in self.products), 60.0)

    def test_per_product_variations_add_up_to_the_total(self):
        """The dangerous half: product by product the report used to ask for 220 when only
        160 was actually left to book."""
        self._book_without_product()
        self.assertAlmostEqual(self._variation(), 160.0)
        self.assertAlmostEqual(sum(self._variation(product_ids=p.ids) for p in self.products), 160.0)

    def test_each_filtered_section_stays_coherent(self):
        """Initial Balance + Variation = Ending Stock, per product."""
        self._book_without_product()
        for product in self.products:
            data = self._data(product_ids=product.ids)
            self.assertAlmostEqual(
                data["initial_balance"]["value"] + data["stock_variation"]["value"],
                data["ending_stock"]["value"],
                msg=f"Sections do not add up for {product.name}",
            )

    # -- The criterion ---------------------------------------------------------
    def test_share_follows_the_pending_gap(self):
        """Nothing booked yet, so each gap equals the inventory value: 60 shared out over
        100 / 100 / 20."""
        self._book_without_product()
        self.assertAlmostEqual(self._initial(product_ids=self.product_standard.ids), 60.0 * 100 / 220)
        self.assertAlmostEqual(self._initial(product_ids=self.product_avco.ids), 60.0 * 100 / 220)
        self.assertAlmostEqual(self._initial(product_ids=self.product_fifo.ids), 60.0 * 20 / 220)

    def test_a_product_with_no_gap_left_claims_nothing(self):
        """The reason the weight is the gap and not the plain inventory value: once a
        product is booked at its inventory value it must stop claiming a share, or closing
        the products one by one books more than the full closing."""
        self._book_without_product()
        # Book the standard product on its own: its gap goes to zero.
        self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        share = self.company._get_unattributed_accounting_share(
            self.account_stock_valuation, self.products, self.product_standard
        )
        self.assertAlmostEqual(share, 0.0, msg="Nothing pending, nothing claimed")
        rest = self.company._get_unattributed_accounting_share(
            self.account_stock_valuation, self.products, self.product_avco + self.product_fifo
        )
        self.assertAlmostEqual(rest, 1.0, msg="The whole leftover is for what is still pending")

    def test_shares_of_a_partition_add_up_to_one(self):
        """Whatever the split of the account's products, the shares add up to 1: that is
        the property the coherence of the report rests on."""
        share_one = self.company._get_unattributed_accounting_share(
            self.account_stock_valuation, self.products, self.product_standard
        )
        share_rest = self.company._get_unattributed_accounting_share(
            self.account_stock_valuation, self.products, self.product_avco + self.product_fifo
        )
        self.assertAlmostEqual(share_one + share_rest, 1.0)

    def test_share_without_products_in_the_account_is_zero(self):
        self.assertAlmostEqual(
            self.company._get_unattributed_accounting_share(
                self.account_stock_valuation, self.env["product.product"], self.products
            ),
            0.0,
        )
        self.assertAlmostEqual(
            self.company._get_unattributed_accounting_share(
                self.account_stock_valuation, self.product_standard, self.product_avco
            ),
            0.0,
            msg="A product of another account claims nothing",
        )

    def test_share_falls_back_to_the_product_count_without_a_pending_gap(self):
        """With no gap to weigh (everything booked, the leftover is a balance to write
        off), the weight is the count, which keeps the same adding-up property."""
        valueless = self.env["product.product"].create(
            [
                {"name": "Valueless A", "is_storable": True, "categ_id": self.category_standard.id},
                {"name": "Valueless B", "is_storable": True, "categ_id": self.category_standard.id},
            ]
        )
        self.assertAlmostEqual(
            self.company._get_unattributed_accounting_share(self.account_stock_valuation, valueless, valueless[0]),
            0.5,
        )
        self.assertAlmostEqual(
            self.company._get_unattributed_accounting_share(self.account_stock_valuation, valueless, valueless),
            1.0,
        )

    # -- Effect on the entries -------------------------------------------------
    def test_closing_product_by_product_does_not_book_the_portion_twice(self):
        """Closing each product in turn has to book the same total as one full closing:
        160, not 220."""
        self._book_without_product()
        booked = 0.0
        for product in self.products:
            action = self.company.action_close_stock_valuation(auto_post=True, product_ids=product.ids)
            entry = self.env["account.move"].browse(action["res_id"])
            lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
            booked += sum(lines.mapped("debit")) - sum(lines.mapped("credit"))
        # Rounding to the currency precision on each of the three entries, hence the delta.
        self.assertAlmostEqual(booked, 160.0, delta=0.05)
        # And the account ends at the real inventory value.
        self.assertAlmostEqual(self._initial(), 220.0)
        self.assertAlmostEqual(self._variation(), 0.0)

    def test_partial_closing_books_the_product_net_of_its_share(self):
        self._book_without_product()
        action = self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        entry = self.env["account.move"].browse(action["res_id"])
        lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        net = sum(lines.mapped("debit")) - sum(lines.mapped("credit"))
        self.assertAlmostEqual(net, self.company.currency_id.round(100.0 - 60.0 * 100 / 220))

    def test_full_closing_leaves_nothing_unattributed(self):
        """The full closing keeps healing the data: its residual line cancels the
        unattributed portion, so the sharing out becomes inert."""
        self._book_without_product()
        self._close()
        self.assertFalse(
            self.company._get_unattributed_accounting_value(self.account_stock_valuation),
            "Nothing left with no product",
        )
        self.assertAlmostEqual(self._initial(), 220.0)
        self.assertAlmostEqual(sum(self._initial(product_ids=p.ids) for p in self.products), 220.0)

    # -- Regression ------------------------------------------------------------
    def test_without_unattributed_balance_nothing_changes(self):
        """No unattributed portion, no sharing out: the filtered Initial Balance is the
        balance booked for those products and nothing else."""
        self._close()
        self.assertFalse(self.company._get_unattributed_accounting_value(self.account_stock_valuation))
        self.assertAlmostEqual(self._initial(product_ids=self.product_standard.ids), 100.0)
        self.assertAlmostEqual(self._initial(product_ids=self.product_avco.ids), 100.0)
        self.assertAlmostEqual(self._initial(product_ids=self.product_fifo.ids), 20.0)

    def test_cut_off_date_is_honoured(self):
        """The unattributed portion is read up to the cut-off date, like every other
        balance the report reads."""
        today = self.env.cr.now().date()
        entry = self._book_without_product(date=today - relativedelta(days=10))
        self.assertEqual(entry.state, "posted", "A future date would stay in draft and prove nothing")
        account = self.account_stock_valuation
        self.assertFalse(
            self.company._get_unattributed_accounting_value(account, today - relativedelta(days=20)),
            "Before the entry there is nothing to share out",
        )
        self.assertAlmostEqual(sum(self.company._get_unattributed_accounting_value(account, today).values()), 60.0)
        # With no cut-off the report shares it out over the products.
        self.assertAlmostEqual(sum(self._initial(product_ids=p.ids) for p in self.products), 60.0)
