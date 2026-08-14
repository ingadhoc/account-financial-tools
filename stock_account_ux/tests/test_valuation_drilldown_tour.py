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

    def _setup_pending_variation(self):
        """Leave a valued, unaccounted move in the admin's company: that is what makes the
        report draw an account line in the Variation, and with no line there is no menu to
        click."""
        company = self.env.ref("base.user_admin").company_id
        env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
        env = env["res.company"].with_company(company).env

        valuation_account = env["account.account"].create(
            {
                "name": "Test Drilldown Stock Valuation",
                "code": "TDSV01",
                "account_type": "asset_current",
            }
        )
        valuation_account.account_stock_variation_id = env["account.account"].create(
            {
                "name": "Test Drilldown Stock Variation",
                "code": "TDSV02",
                "account_type": "expense",
            }
        )
        category = env["product.category"].create(
            {
                "name": "Test Drilldown Category",
                "property_valuation": "periodic",
                "property_cost_method": "average",
                "property_stock_valuation_account_id": valuation_account.id,
            }
        )
        product = env["product.product"].create(
            {
                "name": "Test Drilldown Product",
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
        return move

    def test_variation_drilldown(self):
        move = self._setup_pending_variation()
        self.assertFalse(move.related_account_move_id, "It has to stay unaccounted")
        self.start_tour(
            "/odoo/stock-valuation-closing",
            "stock_account_ux_valuation_drilldown",
            login="admin",
        )

    def test_filters_survive_the_drilldown(self):
        """Going to the detail and back through the breadcrumb must not clear the filters."""
        self._setup_pending_variation()
        self.start_tour(
            "/odoo/stock-valuation-closing",
            "stock_account_ux_valuation_filters_kept",
            login="admin",
        )
