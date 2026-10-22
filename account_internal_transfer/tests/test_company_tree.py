# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCompanyTree(AccountTestInvoicingCommon):
    """Three levels: root -> region -> branch, plus a sibling region."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.root = cls.company_data["company"]
        cls.region = Company.create({"name": "Region A", "parent_id": cls.root.id})
        cls.other_region = Company.create({"name": "Region B", "parent_id": cls.root.id})
        cls.branch = Company.create({"name": "Branch A1", "parent_id": cls.region.id})

    def test_destination_companies_cover_the_whole_tree(self):
        payment = self.env["account.payment"].new({"company_id": self.branch.id, "is_internal_transfer": True})

        self.assertEqual(payment.main_company_id, self.root)
        destinations = self.env["res.company"].search(
            ["|", ("id", "parent_of", payment.main_company_id.id), ("id", "child_of", payment.main_company_id.id)]
        )
        self.assertIn(self.other_region, destinations, "A sibling region has to be offered as destination.")
        self.assertIn(self.root, destinations)
