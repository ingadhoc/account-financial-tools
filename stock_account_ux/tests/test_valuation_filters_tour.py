from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "stock_account_ux_tour")
class TestValuationFiltersTour(HttpCase):
    """Drive the report in a real browser and check that a filter selection sticks and is
    not cleared."""

    def test_valuation_filters_persist(self):
        self.start_tour(
            "/odoo/stock-valuation-closing",
            "stock_account_ux_valuation_filters",
            login="admin",
        )
