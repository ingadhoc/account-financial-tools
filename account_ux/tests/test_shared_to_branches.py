# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSharedToBranches(TransactionCase):
    """How far down a branch tree a record of the parent company reaches.

    Three values on one axis — *all branches* / *same legal entity* / *not shared* — and
    *same legal entity* answered with the single criterion of ``legal_entity_root_id``.

    The tree is the one that motivated the whole thing: a parent with a real branch that
    declares the same Tax ID, and an auxiliary company with none of its own, which is
    therefore a different legal entity.

    Companies are created without a country on purpose: ``base_vat`` only validates the Tax
    ID format when it can tell the country, so the test values pass as they are and the test
    does not depend on any localization.
    """

    PARENT_VAT = "30111111118"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.company"].create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.branch = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.aux = cls.env["res.company"].create({"name": "Auxiliar sin CUIT", "parent_id": cls.parent.id, "vat": False})
        cls.parent_journal = cls._create_journal(cls.parent, "PAR")

    @classmethod
    def _create_journal(cls, company, code, journal_type="general", **context):
        """A journal with its account created by hand.

        These companies have no chart of accounts, so nothing fills the default account for us.
        """
        account = cls.env["account.account"].create(
            {
                "name": "Cuenta de prueba %s" % code,
                "code": "9%s" % code,
                "account_type": "asset_current",
                "company_ids": [(6, 0, company.ids)],
            }
        )
        return (
            cls.env["account.journal"]
            .with_context(**context)
            .create(
                {
                    "name": "Diario %s" % code,
                    "code": code,
                    "type": journal_type,
                    "company_id": company.id,
                    "default_account_id": account.id,
                }
            )
        )

    def _set_scope(self, scope):
        self.parent_journal.shared_to_branches = scope

    # -------------------------------------------------------------------------
    # Where a new record gets its scope from
    # -------------------------------------------------------------------------

    def test_a_new_journal_takes_its_scope_from_its_type(self):
        """The journal's scope comes from its compute, and nothing may take its place.

        A ``default`` on the field —even one inherited from the mixin— would count as a given
        value and skip the compute, and purchase journals would silently stop being shared.
        ``demo`` in the context is what turns off the "share everything" shortcut the compute
        takes while running tests.
        """
        purchase = self._create_journal(self.parent, "TCO", journal_type="purchase", demo=True)
        sale = self._create_journal(self.parent, "TVE", journal_type="sale", demo=True)
        self.assertEqual(purchase.shared_to_branches, "all")
        self.assertEqual(sale.shared_to_branches, "none")

    def test_a_new_fiscal_position_reaches_every_branch(self):
        """What a fiscal position did before the field existed, so nothing changes by default."""
        fpos = self.env["account.fiscal.position"].create({"name": "PF nueva", "company_id": self.parent.id})
        self.assertEqual(fpos.shared_to_branches, "all")

    # -------------------------------------------------------------------------
    # The Python answer: _is_shared_to_company
    # -------------------------------------------------------------------------

    def test_own_company_always_reaches_the_record(self):
        """Whatever the scope says, the company that owns the record can use it."""
        for scope in ("all", "legal_entity", "none"):
            self._set_scope(scope)
            self.assertTrue(self.parent_journal._is_shared_to_company(self.parent), scope)

    def test_all_branches_reaches_every_branch(self):
        self._set_scope("all")
        self.assertTrue(self.parent_journal._is_shared_to_company(self.branch))
        self.assertTrue(self.parent_journal._is_shared_to_company(self.aux))

    def test_legal_entity_leaves_the_auxiliary_out(self):
        """The point of the whole task: same Tax ID in, no Tax ID of its own out."""
        self._set_scope("legal_entity")
        self.assertTrue(self.parent_journal._is_shared_to_company(self.branch))
        self.assertFalse(self.parent_journal._is_shared_to_company(self.aux))

    def test_not_shared_reaches_no_branch(self):
        self._set_scope("none")
        self.assertFalse(self.parent_journal._is_shared_to_company(self.branch))
        self.assertFalse(self.parent_journal._is_shared_to_company(self.aux))

    def test_a_company_outside_the_tree_never_reaches_the_record(self):
        """Sharing is about descendants; being the same legal entity is not enough."""
        outsider = self.env["res.company"].create({"name": "Ajena", "vat": self.PARENT_VAT})
        self._set_scope("all")
        self.assertFalse(self.parent_journal._is_shared_to_company(outsider))

    # -------------------------------------------------------------------------
    # The domain answer: _check_company_domain
    # -------------------------------------------------------------------------

    def _journals_available_to(self, company):
        Journal = self.env["account.journal"]
        return Journal.search(Journal._check_company_domain(company))

    def test_company_domain_matches_the_python_answer(self):
        """The two ways of resolving the scope have to agree, company by company."""
        for scope in ("all", "legal_entity", "none"):
            self._set_scope(scope)
            for company in (self.parent, self.branch, self.aux):
                with self.subTest(scope=scope, company=company.name):
                    self.assertEqual(
                        self.parent_journal in self._journals_available_to(company),
                        self.parent_journal._is_shared_to_company(company),
                    )

    def test_company_domain_with_several_companies_does_not_mix_entities(self):
        """Two companies of different entities asking together must not lend each other the match.

        With the auxiliary and the real branch selected at the same time, the journal is
        available because of the branch — but that must not make it available *to* the
        auxiliary, which is what the per-company check above pins down.
        """
        self._set_scope("legal_entity")
        both = self.branch | self.aux
        self.assertIn(self.parent_journal, self._journals_available_to(both))
        self.assertNotIn(self.parent_journal, self._journals_available_to(self.aux))

    # -------------------------------------------------------------------------
    # The record rule: what a branch user actually sees
    # -------------------------------------------------------------------------

    def _user_of(self, company):
        return self.env["res.users"].create(
            {
                "name": "Usuario %s" % company.name,
                "login": "user_%s" % company.id,
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("account.group_account_user").id,
                            self.env.ref("base.group_multi_company").id,
                        ],
                    )
                ],
            }
        )

    def test_record_rule_follows_the_scope(self):
        """The rule has to say the same thing as the company domain, or the journal is
        either invisible where it should be usable, or listed where it is not."""
        branch_user = self._user_of(self.branch)
        aux_user = self._user_of(self.aux)

        self._set_scope("all")
        self.assertIn(self.parent_journal, self.env["account.journal"].with_user(branch_user).search([]))
        self.assertIn(self.parent_journal, self.env["account.journal"].with_user(aux_user).search([]))

        self._set_scope("legal_entity")
        self.assertIn(self.parent_journal, self.env["account.journal"].with_user(branch_user).search([]))
        self.assertNotIn(self.parent_journal, self.env["account.journal"].with_user(aux_user).search([]))

        self._set_scope("none")
        self.assertNotIn(self.parent_journal, self.env["account.journal"].with_user(branch_user).search([]))
        self.assertNotIn(self.parent_journal, self.env["account.journal"].with_user(aux_user).search([]))

    # -------------------------------------------------------------------------
    # Fiscal positions: the seam is the autodetection
    # -------------------------------------------------------------------------

    def _autodetected_in(self, company, partner):
        return self.env["account.fiscal.position"].with_company(company)._get_fiscal_position(partner)

    def test_fiscal_position_autodetection_follows_the_scope(self):
        country = self.env.ref("base.uy")
        partner = self.env["res.partner"].create({"name": "Cliente", "country_id": country.id})
        fpos = self.env["account.fiscal.position"].create(
            {
                "name": "PF de la padre",
                "company_id": self.parent.id,
                "auto_apply": True,
                "vat_required": False,
                "country_id": country.id,
            }
        )

        fpos.shared_to_branches = "all"
        self.assertEqual(self._autodetected_in(self.branch, partner), fpos)
        self.assertEqual(self._autodetected_in(self.aux, partner), fpos)

        fpos.shared_to_branches = "legal_entity"
        self.assertEqual(self._autodetected_in(self.branch, partner), fpos)
        self.assertFalse(self._autodetected_in(self.aux, partner))

        fpos.shared_to_branches = "none"
        self.assertFalse(self._autodetected_in(self.branch, partner))
        self.assertFalse(self._autodetected_in(self.aux, partner))
        # The company that owns it keeps autodetecting it, whatever the scope.
        self.assertEqual(self._autodetected_in(self.parent, partner), fpos)

    def test_fiscal_position_stays_selectable_when_it_does_not_autodetect(self):
        """Only the automatic match is scoped: the company domain is untouched on purpose,
        so the documents of a branch that already reference the parent's position keep
        passing their company check."""
        fpos = self.env["account.fiscal.position"].create(
            {"name": "PF de la padre", "company_id": self.parent.id, "shared_to_branches": "none"}
        )
        FiscalPosition = self.env["account.fiscal.position"]
        self.assertIn(fpos, FiscalPosition.search(FiscalPosition._check_company_domain(self.aux)))
