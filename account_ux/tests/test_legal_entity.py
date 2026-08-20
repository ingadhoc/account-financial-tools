# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalEntity(TransactionCase):
    """Criterio único de "misma entidad fiscal" sobre un árbol de sucursales.

    La regla es igualdad literal y explícita del CUIT, sin herencia: un CUIT vacío
    NO toma el del padre, y ``/`` tampoco — es la declaración explícita de "soy otra
    entidad". Es la divergencia deliberada con el criterio nativo de Enterprise
    (``_get_branches_with_same_vat``), que considera el CUIT vacío igual al del
    ancestro más cercano y por eso mete a la auxiliar sin CUIT adentro del grupo
    fiscal de la padre.

    Las compañías se crean sin país a propósito: ``base_vat`` solo valida el formato
    del CUIT cuando puede determinar un país (``_run_vat_checks``), así que sin país
    los valores de prueba pasan tal cual y el test no depende de la localización.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30222222227"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.company"].create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.same_vat = cls._create_branch("Sucursal mismo CUIT", cls.parent, cls.PARENT_VAT)
        cls.no_vat = cls._create_branch("Auxiliar sin CUIT", cls.parent, False)
        cls.slash_vat = cls._create_branch("Auxiliar con barrita", cls.parent, "/")
        cls.other_vat = cls._create_branch("Otra razón social", cls.parent, cls.OTHER_VAT)

    @classmethod
    def _create_branch(cls, name, parent, vat):
        return cls.env["res.company"].create({"name": name, "parent_id": parent.id, "vat": vat})

    def test_same_explicit_vat_is_same_entity(self):
        self.assertEqual(self.same_vat.legal_entity_root_id, self.parent)

    def test_empty_vat_is_its_own_entity(self):
        """El caso que motivó todo: la auxiliar sin CUIT no entra al grupo de la padre."""
        self.assertEqual(self.no_vat.legal_entity_root_id, self.no_vat)

    def test_slash_vat_is_its_own_entity(self):
        self.assertEqual(self.slash_vat.legal_entity_root_id, self.slash_vat)

    def test_different_vat_is_its_own_entity(self):
        self.assertEqual(self.other_vat.legal_entity_root_id, self.other_vat)

    def test_two_companies_without_valid_vat_are_not_the_same_entity(self):
        """Ni entre ellas: no tener CUIT válido no agrupa, deja sola a cada una.

        Vale para vacío contra vacío y para vacío contra ``/``, que en intención no
        son lo mismo aunque las dos queden solas.
        """
        second_no_vat = self._create_branch("Otra auxiliar sin CUIT", self.parent, False)
        self.assertNotEqual(self.no_vat.legal_entity_root_id, second_no_vat.legal_entity_root_id)
        self.assertNotEqual(self.no_vat.legal_entity_root_id, self.slash_vat.legal_entity_root_id)

    def test_entity_head_propagates_down_an_unbroken_chain(self):
        grandchild = self._create_branch("Sub-sucursal mismo CUIT", self.same_vat, self.PARENT_VAT)
        self.assertEqual(grandchild.legal_entity_root_id, self.parent)

    def test_entity_head_is_recomputed_when_the_parent_vat_changes(self):
        """El campo es stored: si cambia el CUIT de la padre, las hijas se recalculan."""
        self.parent.vat = self.OTHER_VAT
        self.assertEqual(self.same_vat.legal_entity_root_id, self.same_vat)
        self.assertEqual(self.other_vat.legal_entity_root_id, self.parent)

    def test_get_legal_entity_companies(self):
        grandchild = self._create_branch("Sub-sucursal mismo CUIT", self.same_vat, self.PARENT_VAT)
        group = self.parent._get_legal_entity_companies()
        self.assertEqual(group, self.parent | self.same_vat | grandchild)
        # Contrato del método nativo que overrideamos: self va primero, porque los
        # llamadores usan el resultado para restaurar la compañía activa.
        self.assertEqual(group[0], self.parent)
        self.assertEqual(self.same_vat._get_legal_entity_companies()[0], self.same_vat)

    def test_get_legal_entity_companies_excludes_other_entities(self):
        for company in (self.no_vat, self.slash_vat, self.other_vat):
            self.assertEqual(company._get_legal_entity_companies(), company)

    def test_vat_cannot_reappear_after_a_break_in_the_chain(self):
        """Padre 123 / hija sin CUIT / nieta 123 no es una configuración válida.

        Si se permitiera, "¿la nieta es la misma entidad que la padre?" tendría dos
        respuestas defendibles según hasta dónde se mire.
        """
        with self.assertRaises(ValidationError):
            self._create_branch("Nieta que revive el CUIT", self.no_vat, self.PARENT_VAT)

    def test_vat_cannot_reappear_below_a_break_declared_with_a_slash(self):
        with self.assertRaises(ValidationError):
            self._create_branch("Nieta que revive el CUIT", self.slash_vat, self.PARENT_VAT)

    def test_the_clash_is_also_detected_when_it_is_created_from_above(self):
        """Se puede romper editando el CUIT de arriba, no solo creando abajo."""
        grandchild = self._create_branch("Nieta con CUIT propio", self.no_vat, self.OTHER_VAT)
        self.assertEqual(grandchild.legal_entity_root_id, grandchild)
        with self.assertRaises(ValidationError):
            self.parent.vat = self.OTHER_VAT

    def test_a_branch_cannot_be_moved_at_all(self):
        """Por qué el constraint solo tiene que cubrir el create y la edición del CUIT.

        La jerarquía es inmutable: core rechaza ``parent_id`` en cualquier ``write``
        (``res_company.write`` → "The company hierarchy cannot be changed"), así que una
        sucursal nunca se recuelga de otra padre. Si esto cambiara aguas arriba, este
        test se rompe y hay que volver a mirar el constraint.
        """
        orphan = self.env["res.company"].create({"name": "Suelta", "vat": self.PARENT_VAT})
        with self.assertRaises(UserError):
            orphan.parent_id = self.no_vat

    def test_repeating_the_vat_without_a_break_is_valid(self):
        """La regla prohíbe reaparecer después de un corte, no repetir el CUIT."""
        chain = self._create_branch("Sub-sucursal mismo CUIT", self.same_vat, self.PARENT_VAT)
        self.assertEqual(chain.legal_entity_root_id, self.parent)


@tagged("post_install", "-at_install")
class TestLegalEntityCompanyCheck(TransactionCase):
    """``account.move.line`` acepta ser usado dentro de toda su entidad fiscal.

    El default de Odoo para este modelo es el estricto —solo la compañía dueña del
    apunte— y es simétrico: un pago de una sucursal no puede tomar un apunte de su
    padre, ni el de la padre uno de la sucursal. Como la deuda de una entidad fiscal
    se cobra desde cualquiera de sus compañías, el chequeo de consistencia tiene que
    responder con el mismo criterio que todo lo demás.

    Lo que se relaja es el límite entre sucursales de una entidad; el límite entre
    entidades distintas sigue en pie, y eso es lo que estos tests fijan.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30222222226"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env["res.company"]
        cls.parent = Company.create({"name": "Casa Matriz", "vat": cls.PARENT_VAT})
        cls.same_entity = Company.create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.other_entity = Company.create(
            {"name": "Sucursal otro CUIT", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )
        cls.line = cls.env["account.move.line"]

    def _accepted_company_ids(self, companies):
        """Los ids que el dominio de consistencia deja pasar, sin el ``False``."""
        domain = self.line._check_company_domain(companies)
        return {
            company_id
            for condition in domain.iter_conditions()
            for company_id in (condition.value if isinstance(condition.value, (list, tuple)) else [condition.value])
            if company_id
        }

    def test_the_whole_legal_entity_is_accepted_from_a_branch(self):
        """Es el caso que el default rechazaba: el pago de la sucursal toma deuda del padre."""
        self.assertEqual(
            self._accepted_company_ids(self.same_entity),
            {self.same_entity.id, self.parent.id},
        )

    def test_the_whole_legal_entity_is_accepted_from_the_parent(self):
        """Y al revés, que es lo que ``parent_of`` no daría: la padre cobra lo de su sucursal."""
        self.assertEqual(
            self._accepted_company_ids(self.parent),
            {self.parent.id, self.same_entity.id},
        )

    def test_another_legal_entity_is_not_accepted(self):
        """La garantía que se conserva: la sucursal con otro CUIT queda afuera."""
        self.assertEqual(self._accepted_company_ids(self.other_entity), {self.other_entity.id})
        self.assertNotIn(self.other_entity.id, self._accepted_company_ids(self.parent))

    def test_no_company_still_means_no_company(self):
        """Sin compañías el contrato del default no cambia."""
        self.assertEqual(
            repr(self.line._check_company_domain(self.env["res.company"])),
            repr(self.line._check_company_domain(False)),
        )
