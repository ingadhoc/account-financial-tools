from odoo.addons.stock_account.tests.common import TestStockValuationCommon


class TestStockValuationUXCommon(TestStockValuationCommon):
    # Run as the superuser, as in 19: the tests exercise the valuation, not access rights.
    _test_user_groups = ()
