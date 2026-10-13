# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestParentAccounts(AccountTestInvoicingCommon):
    """Una cuenta con hijas solo agrupa: queda archivada, como los grupos que el core migró a cuentas padre."""

    def _new_account(self, code, **vals):
        return self.env["account.account"].create(
            {"code": code, "name": f"Cuenta {code}", "account_type": "asset_current", **vals}
        )

    def test_assigning_a_parent_archives_it(self):
        parent = self._new_account("9100")
        child = self._new_account("9101", parent_id=parent.id)
        self.assertFalse(parent.active)

        other_parent = self._new_account("9200")
        child.parent_id = other_parent
        self.assertFalse(other_parent.active)

    def test_archived_parent_cannot_be_used_in_entries(self):
        parent = self._new_account("9100")
        self._new_account("9101", parent_id=parent.id)
        move = self.env["account.move"].create(
            {
                "line_ids": [
                    (0, 0, {"account_id": self.company_data["default_account_revenue"].id, "credit": 10.0}),
                    (0, 0, {"account_id": self.company_data["default_account_assets"].id, "debit": 10.0}),
                ]
            }
        )
        with self.assertRaises(UserError):
            move.line_ids[1].account_id = parent

    def test_parent_with_children_cannot_be_unarchived(self):
        parent = self._new_account("9100")
        self._new_account("9101", parent_id=parent.id)
        with self.assertRaises(UserError):
            parent.active = True

    def test_account_with_entries_cannot_become_parent(self):
        used = self.company_data["default_account_revenue"]
        self.init_invoice("out_invoice", amounts=[100.0], post=True)
        with self.assertRaises(UserError):
            self._new_account("9101", parent_id=used.id)
        self.assertTrue(used.active)

    def test_account_without_children_can_be_unarchived(self):
        parent = self._new_account("9100")
        child = self._new_account("9101", parent_id=parent.id)
        child.parent_id = False
        parent.active = True
        self.assertTrue(parent.active)
