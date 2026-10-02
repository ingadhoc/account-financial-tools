from dateutil.relativedelta import relativedelta
from odoo import Command
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestInitialBalanceAttribution(TestStockValuationCommon):
    """Initial Balance of the report while a product filter is active.

    Criterion: filtered, the report brings ONLY the journal items whose product is set and
    matches the filter, so it can be checked against the journal items grouped by product.
    The balance no product can claim (no product, or a non-storable one) shows up only in
    the unfiltered report, and a closing filtered by product is refused while it exists.

    Scenario: three periodic products sharing the valuation account, with inventory values
    of 100 / 100 / 20.
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

    def _book_on_valuation(self, amount=60.0, product=None, date=None):
        """Entry on the valuation account, with no product by default: that is how the
        standard closing books, how a migrated base brings its opening balance and how an
        accountant posts by hand."""
        counterpart = self.account_stock_valuation.account_stock_variation_id or self.company.expense_account_id
        entry = self.env["account.move"].create(
            {
                "journal_id": self.company.account_stock_journal_id.id,
                "date": date or self.env.cr.now().date(),
                "ref": "Booked by hand",
                "company_id": self.company.id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.account_stock_valuation.id,
                            "debit": amount,
                            "credit": 0.0,
                            "product_id": product.id if product else False,
                        }
                    ),
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

    def _valuation_balance(self, entry):
        lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        return sum(lines.mapped("debit")) - sum(lines.mapped("credit"))

    def _close_filtered(self, **filters):
        action = self.company.action_close_stock_valuation(auto_post=True, **filters)
        return self.env["account.move"].browse(action["res_id"])

    # -- The filtered Initial Balance is the journal items of the filter ---------
    def test_balance_with_no_product_is_left_out_of_the_filtered_report(self):
        self._book_on_valuation()
        self.assertAlmostEqual(self._initial(), 60.0, msg="Unfiltered, the whole account balance")
        for product in self.products:
            self.assertAlmostEqual(self._initial(product_ids=product.ids), 0.0, msg=product.name)
        self.assertAlmostEqual(self._initial(product_ids=self.products.ids), 0.0, msg="Not shared out either")

    def test_filtered_initial_balance_matches_the_journal_items(self):
        self._close()
        self._book_on_valuation(5.0, product=self.product_standard)
        self._book_on_valuation(40.0)
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.account_stock_valuation.id),
                ("parent_state", "=", "posted"),
                ("product_id", "=", self.product_standard.id),
            ]
        )
        self.assertAlmostEqual(self._initial(product_ids=self.product_standard.ids), sum(lines.mapped("balance")))
        self.assertAlmostEqual(self._initial(product_ids=self.product_standard.ids), 105.0)
        self.assertAlmostEqual(
            self._initial(categ_ids=self.category_standard.ids), 105.0, msg="Same through the category"
        )

    def test_filtered_report_still_adds_up(self):
        """Initial Balance + Variation = Ending Stock, per product."""
        self._book_on_valuation()
        for product in self.products:
            data = self._data(product_ids=product.ids)
            self.assertAlmostEqual(
                data["initial_balance"]["value"] + data["stock_variation"]["value"],
                data["ending_stock"]["value"],
                msg=f"Sections do not add up for {product.name}",
            )

    def test_non_storable_product_balance_is_left_out(self):
        """A non-storable product with journal items on the valuation account is not part
        of the inventory: no filter claims it, and it counts as unattributed."""
        consumable = self.env["product.product"].create(
            {"name": "Fee", "type": "consu", "is_storable": False, "categ_id": self.category_standard.id}
        )
        self._close()
        self._book_on_valuation(7.0, product=consumable)
        self.assertAlmostEqual(self._initial(), 227.0)
        self.assertAlmostEqual(self._initial(categ_ids=self.category_standard.ids), 100.0)
        unattributed = self.company._get_unattributed_accounting_value(self.account_stock_valuation)
        self.assertAlmostEqual(unattributed[self.account_stock_valuation], 7.0)

    def test_product_without_stock_brings_its_balance(self):
        """A product with no stock at the date is not in the valued products, but its
        journal items are still on the account: the filtered report has to bring them."""
        self._close()
        self._make_out_move(self.product_standard, 10)
        self.assertFalse(self.product_standard.qty_available)
        data = self._data(product_ids=self.product_standard.ids)
        self.assertAlmostEqual(data["initial_balance"]["value"], 100.0)
        self.assertAlmostEqual(data["ending_stock"]["value"], 0.0)
        # The section value adds up the debits only, so the sign is read on the account line.
        valuation_line = next(
            line for line in data["stock_variation"]["lines"] if line["account_id"] == self.account_stock_valuation.id
        )
        self.assertAlmostEqual(valuation_line["debit"] - valuation_line["credit"], -100.0)
        self.assertAlmostEqual(self._initial(categ_ids=self.category_standard.ids), 100.0)

    def test_archived_product_brings_its_balance(self):
        self._close()
        self._make_out_move(self.product_standard, 10)
        self.product_standard.action_archive()
        self.assertAlmostEqual(self._initial(categ_ids=self.category_standard.ids), 100.0)

    def test_filtered_product_by_product_adds_up_to_the_journal_items(self):
        """With no unattributed balance, filtering product by product adds up to the
        unfiltered report."""
        self._close()
        self._make_out_move(self.product_standard, 10)
        self.product_standard.action_archive()
        self.assertAlmostEqual(sum(self._initial(product_ids=p.ids) for p in self.products), self._initial())

    # -- Drill-down of the Initial Balance --------------------------------------
    def test_ledger_drilldown_opens_the_filtered_journal_items(self):
        self._close()
        self._book_on_valuation(40.0)
        action = self.report.action_open_account_ledger(
            self.account_stock_valuation.id, filters={"product_ids": self.product_avco.ids}
        )
        self.assertEqual(action["res_model"], "account.move.line")
        lines = self.env["account.move.line"].search(action["domain"])
        self.assertEqual(lines.product_id, self.product_avco)
        self.assertAlmostEqual(
            sum(lines.mapped("balance")), self._initial(product_ids=self.product_avco.ids), msg="Same as the line"
        )

    # -- Closing entry ------------------------------------------------------------
    def test_partial_closing_is_refused_with_unattributed_balance(self):
        """It would book the unattributed balance again on top of the entry it came from."""
        self._book_on_valuation()
        with self.assertRaises(UserError):
            self.company.action_close_stock_valuation(auto_post=True, product_ids=self.product_standard.ids)
        with self.assertRaises(UserError):
            self.company.action_close_stock_valuation(auto_post=True, categ_ids=self.category_standard.ids)

    def test_unfiltered_closings_are_not_refused(self):
        """The full closing and the one filtered by Movement Type only take the whole
        account balance, so they do not need the check."""
        self._book_on_valuation()
        self.company.action_close_stock_valuation(auto_post=True, line_types=["stock_move"])
        self._close()
        self.assertFalse(
            self.company._get_unattributed_accounting_value(self.account_stock_valuation),
            "The full closing nets the no-product balance",
        )

    def test_partial_closing_is_allowed_once_healed(self):
        self._book_on_valuation()
        self._close()
        self.product_standard.standard_price = 13.0  # 100 -> 130
        entry = self._close_filtered(product_ids=self.product_standard.ids)
        self.assertAlmostEqual(self._valuation_balance(entry), 30.0)

    def test_closing_by_category_books_the_same_as_the_full_closing(self):
        self._close()
        self.product_standard.standard_price = 13.0  # +30
        self._make_in_move(self.product_fifo, 1, 30)  # +30
        pending = self._variation()
        booked = sum(
            self._valuation_balance(self._close_filtered(categ_ids=category.ids))
            for category in (self.category_standard, self.category_fifo)
        )
        self.assertAlmostEqual(booked, pending, delta=0.05)
        self.assertAlmostEqual(self._variation(), 0.0)

    def test_partial_closing_books_a_product_without_stock(self):
        """Its balance is booked back to zero, attributed to the product: nothing is left
        with no product."""
        self._close()
        self._make_out_move(self.product_standard, 10)
        entry = self._close_filtered(product_ids=self.product_standard.ids)
        valuation_lines = entry.line_ids.filtered(lambda line: line.account_id == self.account_stock_valuation)
        self.assertAlmostEqual(self._valuation_balance(entry), -100.0)
        self.assertEqual(valuation_lines.product_id, self.product_standard)
        self.assertFalse(valuation_lines.filtered(lambda line: not line.product_id))
        self.assertAlmostEqual(self._initial(product_ids=self.product_standard.ids), 0.0)

    def test_cut_off_date_is_honoured(self):
        """The unattributed balance is read up to the cut-off date, like every other
        balance the report reads."""
        today = self.env.cr.now().date()
        entry = self._book_on_valuation(date=today - relativedelta(days=10))
        self.assertEqual(entry.state, "posted", "A future date would stay in draft and prove nothing")
        account = self.account_stock_valuation
        self.assertFalse(
            self.company._get_unattributed_accounting_value(account, today - relativedelta(days=20)),
            "Before the entry there is nothing unattributed",
        )
        self.assertAlmostEqual(sum(self.company._get_unattributed_accounting_value(account, today).values()), 60.0)
