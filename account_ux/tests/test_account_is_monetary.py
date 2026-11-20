from odoo.tests import TransactionCase


class TestAccountIsMonetary(TransactionCase):
    def test_retained_earnings_and_other_expenses_are_not_monetary(self):
        """Retained earnings (an account type new in 20.0) and other expenses are equity and results,
        not monetary items, so a remeasurement takes them at the historical rate."""
        for code, account_type, monetary in (
            ("TM001", "equity_retained", False),
            ("TM002", "expense_other", False),
            ("TM003", "asset_receivable", True),
        ):
            account = self.env["account.account"].create(
                {
                    "name": account_type,
                    "code": code,
                    "account_type": account_type,
                    "reconcile": account_type == "asset_receivable",
                }
            )
            self.assertEqual(account.is_monetary, monetary, account_type)
