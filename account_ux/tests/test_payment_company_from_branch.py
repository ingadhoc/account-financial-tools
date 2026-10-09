# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPaymentCompanyFromBranch(AccountTestInvoicingCommon):
    """Qué compañía viaja en el pago hecho desde una factura de otra compañía del árbol.

    Nativamente la compañía sale de la deuda y nunca de dónde está parado el usuario: la
    más superficial de las líneas, o la raíz si vienen de compañías hermanas. Paradas en
    una sucursal, pagar una factura de su propia entidad fiscal le entregaba el pago a la
    padre.

    Con el criterio único: si toda la deuda es de la misma entidad fiscal que la compañía
    activa, el pago es de esa compañía. Si no lo es, viaja la de la deuda, como el nativo.
    """

    PARENT_VAT = "30111111118"
    OTHER_VAT = "30222222226"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.company_data["company"]
        cls.invoice = cls.init_invoice("out_invoice", amounts=[100.0], post=True, company=cls.parent)

        # El CUIT se valida según el país, y este árbol sólo necesita que los CUIT
        # coincidan o no; sin país los valores de prueba pasan tal cual y las fixtures no
        # dependen de ninguna localización, igual que en los tests del criterio.
        cls.parent.country_id = False
        cls.parent.vat = cls.PARENT_VAT
        cls.same_entity = cls.env["res.company"].create(
            {"name": "Sucursal mismo CUIT", "parent_id": cls.parent.id, "vat": cls.PARENT_VAT}
        )
        cls.other_entity = cls.env["res.company"].create(
            {"name": "Sucursal otro CUIT", "parent_id": cls.parent.id, "vat": cls.OTHER_VAT}
        )

    def _wizard_standing_on(self, company):
        """El wizard de pago abierto desde la factura, parado en ``company``."""
        return (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=self.invoice.ids,
                allowed_company_ids=(company + self.parent).ids,
            )
            .create({})
        )

    def test_the_payment_stays_in_the_branch_when_it_is_the_same_legal_entity(self):
        """El caso que cambia: es un pago de la sucursal, no de la padre."""
        self.assertEqual(self._wizard_standing_on(self.same_entity).company_id, self.same_entity)

    def test_the_company_of_the_debt_travels_when_the_branch_is_another_legal_entity(self):
        """Sucursal con otro CUIT: las cuentas no son compatibles, manda la deuda."""
        self.assertEqual(self._wizard_standing_on(self.other_entity).company_id, self.parent)

    def test_standing_on_the_company_of_the_debt_changes_nothing(self):
        self.assertEqual(self._wizard_standing_on(self.parent).company_id, self.parent)

    def _unshare_parent_bank_and_give_the_branch_its_own(self):
        """Lo que trae una base real: el banco de la padre no se comparte, y la sucursal tiene el suyo.

        En modo test todo diario nace compartido a todas las sucursales, así que el escenario se
        arma a mano.
        """
        parent_bank = self.company_data["default_journal_bank"]
        parent_bank.shared_to_branches = "none"
        branch_bank = self.env["account.journal"].create(
            {"name": "Banco sucursal", "code": "BSUC", "type": "bank", "company_id": self.same_entity.id}
        )
        return parent_bank, branch_bank

    def test_the_branch_is_offered_only_the_journals_it_can_use(self):
        parent_bank, branch_bank = self._unshare_parent_bank_and_give_the_branch_its_own()

        wizard = self._wizard_standing_on(self.same_entity)

        self.assertEqual(wizard.journal_id, branch_bank)
        self.assertIn(branch_bank, wizard.available_journal_ids)
        self.assertNotIn(parent_bank, wizard.available_journal_ids)
        payment = wizard._create_payments()
        self.assertEqual(payment.company_id, self.same_entity)
        self.assertEqual(self.invoice.payment_state, self.env["account.move"]._get_invoice_in_payment_state())

    def test_another_legal_entity_keeps_the_journals_of_the_debt(self):
        parent_bank, _branch_bank = self._unshare_parent_bank_and_give_the_branch_its_own()

        wizard = self._wizard_standing_on(self.other_entity)

        self.assertEqual(wizard.company_id, self.parent)
        self.assertIn(parent_bank, wizard.available_journal_ids)
