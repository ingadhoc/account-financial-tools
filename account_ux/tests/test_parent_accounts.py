# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestParentAccounts(AccountTestInvoicingCommon):
    """A parent account only groups: it stays active, but it is not used in entries nor offered as an account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls._new_account("9100")
        cls.child = cls._new_account("9101", parent_id=cls.parent.id)

    @classmethod
    def _new_account(cls, code, **vals):
        return cls.env["account.account"].create(
            {"code": code, "name": f"Cuenta {code}", "account_type": "asset_current", **vals}
        )

    def test_parent_stays_active_and_is_flagged(self):
        self.assertTrue(self.parent.active)
        self.assertTrue(self.parent.is_parent_account)
        self.child.parent_id = False
        self.assertFalse(self.parent.is_parent_account)

    def test_parent_cannot_be_used_in_entries(self):
        move = self.env["account.move"].create(
            {
                "line_ids": [
                    (0, 0, {"account_id": self.company_data["default_account_revenue"].id, "credit": 10.0}),
                    (0, 0, {"account_id": self.parent.id, "debit": 10.0}),
                ]
            }
        )
        with self.assertRaises(UserError):
            move.action_post()

    def test_parent_is_not_offered_when_choosing_an_account(self):
        Account = self.env["account.account"]
        self.assertNotIn(self.parent.id, dict(Account.name_search("9100")))
        self.assertIn(self.parent.id, dict(Account.with_context(show_parent_accounts=True).name_search("9100")))

    def test_archiving_a_parent_detaches_its_children(self):
        self.parent.action_archive()
        self.assertFalse(self.child.parent_id)
        self.assertFalse(self.parent.is_parent_account)

    def test_account_with_entries_cannot_become_parent(self):
        used = self.company_data["default_account_revenue"]
        self.init_invoice("out_invoice", amounts=[100.0], post=True)
        with self.assertRaises(UserError):
            self._new_account("9102", parent_id=used.id)
