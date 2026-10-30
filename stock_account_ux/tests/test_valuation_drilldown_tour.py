from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "stock_account_ux_tour")
class TestValuationDrilldownTour(HttpCase):
    """Drive the report in a real browser and check that the Variation account line offers
    the three-dots menu and navigates to the detail.

    It does NOT use ``TestStockValuationCommon``: that common creates a new company, loads
    ``generic_coa`` into it and reassigns the admin's ``company_ids``. That is no use in an
    HttpCase —the tour runs over HTTP with the admin's real session, so the active company
    is theirs and not the one setUpClass prepared— and it breaks on databases that already
    have a localisation installed. Here the data is created in the ADMIN's company with its
    own accounts, so the tour does not depend on the database's valuation setup.
    """

    def _setup_pending_variation(self, cost_method="average", code="TDSV"):
        """Leave a valued, unaccounted move in the admin's company: that is what makes the
        report draw an account line in the Variation, and with no line there is no menu to
        click."""
        company = self.env.ref("base.user_admin").company_id
        env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
        env = env["res.company"].with_company(company).env

        valuation_account = env["account.account"].create(
            {
                "name": "Test Drilldown Stock Valuation" if cost_method == "average" else f"Test {code} Valuation",
                "code": f"{code}01",
                "account_type": "asset_current",
            }
        )
        valuation_account.account_stock_variation_id = env["account.account"].create(
            {
                "name": f"Test {code} Stock Variation",
                "code": f"{code}02",
                "account_type": "expense",
            }
        )
        category = env["product.category"].create(
            {
                "name": f"Test {code} Category",
                "property_valuation": "periodic",
                "property_cost_method": cost_method,
                "property_stock_valuation_account_id": valuation_account.id,
            }
        )
        product = env["product.product"].create(
            {
                "name": f"Test {code} Product",
                "is_storable": True,
                "type": "consu",
                "categ_id": category.id,
                "standard_price": 40.0,
            }
        )
        warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        move = env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": 5,
                "location_id": env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": warehouse.lot_stock_id.id,
                "company_id": company.id,
            }
        )
        move._action_confirm()
        move.quantity = 5
        move.picked = True
        move._action_done()
        # A cost change is the pending value adjustment the second origin of the menu shows.
        product.standard_price = 50.0
        return move

    def test_variation_drilldown(self):
        move = self._setup_pending_variation()
        self.assertFalse(move.related_account_move_id, "It has to stay unaccounted")
        self.start_tour(
            "/odoo/stock-valuation-closing",
            "stock_account_ux_valuation_drilldown",
            login="admin",
        )

    def test_generate_entries_books_the_filtered_report(self):
        average_move = self._setup_pending_variation()
        standard_move = self._setup_pending_variation(cost_method="standard", code="TDSS")
        self.start_tour(
            "/odoo/stock-valuation-closing",
            "stock_account_ux_valuation_generate_entries",
            login="admin",
        )
        self.assertEqual(average_move.related_account_move_id.state, "posted", "The filtered move is booked")
        self.assertFalse(standard_move.related_account_move_id, "What the filter leaves out stays open")
