# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from lxml import etree
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalEntityFiscalYear(TransactionCase):
    """The fiscal year is delegated to the head of the legal entity, not to the root.

    Core delegates five fields to the root company and forces every branch below it to
    carry the same value (``res_company._get_company_root_delegated_field_names`` and its
    five enforcement points). Two of them, the fiscal year, move to a second tier scoped
    to the legal entity: inside an entity the value is still shared and still enforced,
    and a company that heads its own entity is free and becomes the reference for its own
    subtree.

    Companies are created without a country on purpose: ``base_vat`` only validates the
    format of a Tax ID when it can determine a country, so the test values pass as they
    are and the test does not depend on a localization.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30222222227"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.company"].create(
            {
                "name": "Casa Matriz",
                "vat": cls.PARENT_VAT,
                "fiscalyear_last_day": 30,
                "fiscalyear_last_month": "6",
            }
        )
        cls.same_entity = cls._create_branch("Sucursal mismo CUIT", cls.parent, cls.PARENT_VAT)
        cls.other_entity = cls._create_branch("Otra razón social", cls.parent, cls.OTHER_VAT)
        cls.no_vat = cls._create_branch("Auxiliar sin CUIT", cls.parent, False)

    @classmethod
    def _create_branch(cls, name, parent, vat, **vals):
        return cls.env["res.company"].create({"name": name, "parent_id": parent.id, "vat": vat, **vals})

    def _fiscal_year_of(self, company):
        return (company.fiscalyear_last_day, company.fiscalyear_last_month)

    # ------------------------------------------------------------------
    # Copy on create
    # ------------------------------------------------------------------

    def test_a_new_branch_is_born_with_the_parents_fiscal_year(self):
        """Whatever its Tax ID: for a branch of the entity it is mandatory, for the rest a default."""
        for branch in (self.same_entity, self.other_entity, self.no_vat):
            self.assertEqual(self._fiscal_year_of(branch), (30, "6"), branch.name)

    def test_a_new_branch_of_another_entity_may_be_born_with_its_own_fiscal_year(self):
        branch = self._create_branch(
            "Otra entidad con cierre propio",
            self.parent,
            self.OTHER_VAT + "1",
            fiscalyear_last_day=31,
            fiscalyear_last_month="12",
        )
        self.assertEqual(self._fiscal_year_of(branch), (31, "12"))

    def test_a_new_branch_of_the_entity_cannot_be_born_with_another_fiscal_year(self):
        with self.assertRaises(ValidationError):
            self._create_branch(
                "Sucursal que se desvía",
                self.parent,
                self.PARENT_VAT,
                fiscalyear_last_day=31,
                fiscalyear_last_month="12",
            )

    # ------------------------------------------------------------------
    # The constraint: the warning stays inside the legal entity
    # ------------------------------------------------------------------

    def test_a_branch_of_the_entity_cannot_change_the_fiscal_year(self):
        """This is the warning that has to survive: same legal entity, same fiscal year."""
        with self.assertRaises(ValidationError):
            self.same_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "12"})

    def test_a_branch_of_another_entity_can_change_the_fiscal_year(self):
        """And this is what used to be rejected and now is not."""
        self.other_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "12"})
        self.assertEqual(self._fiscal_year_of(self.other_entity), (31, "12"))
        self.assertEqual(self._fiscal_year_of(self.parent), (30, "6"))

    def test_a_branch_without_tax_id_is_its_own_entity_and_can_change_it_too(self):
        self.no_vat.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "3"})
        self.assertEqual(self._fiscal_year_of(self.no_vat), (31, "3"))

    def test_joining_an_entity_with_another_fiscal_year_is_rejected(self):
        """The Tax ID cannot be used to walk into an entity that closes on another date.

        The constraint watches ``legal_entity_root_id`` and not ``vat`` —a non-stored
        related field cannot be watched— so this is what proves the change of Tax ID is
        covered.
        """
        self.other_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "12"})
        with self.assertRaises(ValidationError):
            self.other_entity.vat = self.PARENT_VAT

    def test_the_entity_can_be_joined_when_the_fiscal_year_already_matches(self):
        self.other_entity.vat = self.PARENT_VAT
        self.assertEqual(self.other_entity.legal_entity_root_id, self.parent)

    # ------------------------------------------------------------------
    # Propagation on write
    # ------------------------------------------------------------------

    def test_the_head_propagates_the_fiscal_year_to_its_entity_only(self):
        self.other_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "12"})
        self.no_vat.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "3"})

        self.parent.write({"fiscalyear_last_day": 30, "fiscalyear_last_month": "9"})

        self.assertEqual(self._fiscal_year_of(self.same_entity), (30, "9"))
        self.assertEqual(self._fiscal_year_of(self.other_entity), (31, "12"))
        self.assertEqual(self._fiscal_year_of(self.no_vat), (31, "3"))

    def test_a_company_that_heads_its_own_entity_is_the_reference_of_its_subtree(self):
        sub = self._create_branch("Sub-sucursal de la otra", self.other_entity, self.OTHER_VAT)
        self.other_entity.write({"fiscalyear_last_day": 31, "fiscalyear_last_month": "12"})

        self.assertEqual(self._fiscal_year_of(sub), (31, "12"))
        self.assertEqual(self._fiscal_year_of(self.parent), (30, "6"))
        with self.assertRaises(ValidationError):
            sub.write({"fiscalyear_last_day": 30, "fiscalyear_last_month": "6"})

    # ------------------------------------------------------------------
    # The rest of the accounting policy travels the same way
    # ------------------------------------------------------------------

    def test_the_whole_accounting_policy_is_shared_inside_the_entity(self):
        """Storno and cash basis are decided by whoever signs the return, same as the year."""
        self.parent.write({"account_storno": True, "tax_exigibility": True})

        self.assertTrue(self.same_entity.account_storno)
        self.assertTrue(self.same_entity.tax_exigibility)
        self.assertFalse(self.other_entity.account_storno)
        self.assertFalse(self.other_entity.tax_exigibility)

    def test_a_branch_of_the_entity_cannot_change_the_accounting_policy(self):
        with self.assertRaises(ValidationError):
            self.same_entity.tax_exigibility = True

    def test_a_branch_of_another_entity_can_change_the_accounting_policy(self):
        self.other_entity.write({"account_storno": True, "tax_exigibility": True})

        self.assertTrue(self.other_entity.account_storno)
        self.assertTrue(self.other_entity.tax_exigibility)
        self.assertFalse(self.parent.account_storno)
        self.assertFalse(self.parent.tax_exigibility)

    # ------------------------------------------------------------------
    # Readonly in the view
    # ------------------------------------------------------------------

    def test_the_field_is_readonly_only_inside_a_legal_entity(self):
        """The fifth enforcement point, on a view built here.

        No view of ``res.company`` shows the fiscal year today —Settings edits it through
        ``res.config.settings``, another model— so the modifier has to be checked on a
        view that does show it, or the mechanism would go untested until somebody adds the
        field and finds out the hard way.
        """
        self.env["ir.ui.view"].create(
            {
                "name": "res.company.form.fiscalyear.test",
                "model": "res.company",
                "inherit_id": self.env.ref("base.view_company_form").id,
                "arch": """
                    <field name="parent_id" position="after">
                        <field name="fiscalyear_last_month"/>
                    </field>
                """,
            }
        )
        arch = etree.fromstring(self.env["res.company"].get_view(view_type="form")["arch"])
        node = arch.find(".//field[@name='fiscalyear_last_month']")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("readonly"), "legal_entity_root_id != id")
        # The modifier is evaluated client side, so the field it reads has to be there.
        self.assertIsNotNone(arch.find(".//field[@name='legal_entity_root_id']"))

    # ------------------------------------------------------------------
    # What did not move
    # ------------------------------------------------------------------

    def test_the_currency_is_still_delegated_to_the_root(self):
        """Only the fiscal year moved tier; under branches the currency stays identical."""
        other_currency = self.env["res.currency"].search([("id", "!=", self.parent.currency_id.id)], limit=1)
        with self.assertRaises(ValidationError):
            self.other_entity.currency_id = other_currency

    def test_the_currency_is_the_only_field_left_delegated_to_the_root(self):
        self.assertEqual(self.parent._get_company_root_delegated_field_names(), ["currency_id"])
