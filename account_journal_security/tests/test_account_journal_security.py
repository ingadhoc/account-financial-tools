import odoo.tests.common as common
from odoo import fields
from odoo.exceptions import AccessError


class TestAccountJournalSecurity(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.company_bank_journal = self.env["account.journal"].search([("type", "=", "bank")], limit=1)
        self.first_company = self.company_bank_journal.company_id

        self.user_admin = self.env.ref("base.user_admin")
        self.user_admin.write({"company_ids": [(4, self.first_company.id)]})
        self.user_demo = self.env.ref("base.user_demo")

        account_user_group = self.env.ref("account.group_account_user")
        self.user_demo.write({"group_ids": [(6, 0, [account_user_group.id])]})

    def _create_account_user(self, login):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": self.first_company.id,
                "company_ids": [(6, 0, [self.first_company.id])],
                "group_ids": [(4, self.env.ref("account.group_account_user").id)],
            }
        )

    def _search_journal_for_payment(self, user):
        """Busca el diario tal como lo hace el selector de diarios de un pago/recibo."""
        return (
            self.env["account.journal"]
            .with_user(user)
            .with_company(self.first_company)
            .with_context(journal_security=True)
            .search([("id", "=", self.company_bank_journal.id)])
        )

    def test_journal_security_varios_usuarios_habilitados(self):
        """Con DOS o mas usuarios habilitados a modificar un diario, cada uno de ellos
        debe seguir viendo ese diario al crear una OP o un recibo, y el resto no.

        Regresion del port a 19.0 (ticket 125244): el filtro traia los diarios donde
        habia CUALQUIER OTRO usuario habilitado y los excluia, con lo cual sobrevivian
        solo los diarios sin restriccion o con un unico usuario habilitado.
        """
        user_allowed_1 = self._create_account_user("journal_security_allowed_1")
        user_allowed_2 = self._create_account_user("journal_security_allowed_2")
        user_restricted = self._create_account_user("journal_security_restricted")

        self.company_bank_journal.write(
            {
                "journal_restriction": "modification",
                "modification_user_ids": [(6, 0, [user_allowed_1.id, user_allowed_2.id])],
            }
        )

        for user in (user_allowed_1, user_allowed_2):
            self.assertIn(
                self.company_bank_journal,
                self._search_journal_for_payment(user),
                "Un usuario habilitado a modificar el diario no lo ve al registrar un pago "
                "cuando hay mas de un usuario habilitado",
            )

        self.assertNotIn(
            self.company_bank_journal,
            self._search_journal_for_payment(user_restricted),
            "Un usuario NO habilitado ve un diario restringido al registrar un pago",
        )

    def test_journal_security_1(self):
        self.company_bank_journal.write(
            {"journal_restriction": "modification", "modification_user_ids": [(4, self.user_admin.id)]}
        )

        # Genero el pago con el diario restringido desde admin
        payment = (
            self.env["account.payment"]
            .with_user(self.user_admin)
            .with_company(self.first_company)
            .create({"journal_id": self.company_bank_journal.id})
        )

        # Desde demo abro el pago y confirmo que puede ingresar
        try:
            payment.with_user(self.user_demo).read()
        except AccessError:
            self.fail(
                "Un usuario restringido con modificación no tiene acceso a pagos de un diario con journal security"
            )

        # Intento confirmar o cancelar el pago con demo
        try:
            payment.with_user(self.user_demo).action_post()
        except AccessError:
            pass  # Si da un error de acceso para un usuario restringido el test está ok
        else:
            self.fail("Un usuario restringido puede confirmar pagos de un diario con journal security")

        try:
            payment.with_user(self.user_demo).action_cancel()
        except AccessError:
            pass
        else:
            self.fail("Un usuario restringido puede cancelar pagos de un diario con journal security")

        # Confirmo el pago con admin
        try:
            payment.with_user(self.user_admin).action_post()
        except AccessError:
            self.fail("Un usuario permitido no puede confirmar los pagos de un diario con journal security")

        # Intento validar, reestablecer a borrador o marcar como enviado con demo
        try:
            payment.with_user(self.user_demo).action_validate()
        except AccessError:
            pass
        else:
            self.fail("Un usuario restringido puede validar pagos de un diario con journal security")

        try:
            payment.with_user(self.user_demo).action_draft()
        except AccessError:
            pass
        else:
            self.fail("Un usuario restringido puede pasar a borrador pagos de un diario con journal security")

        try:
            payment.with_user(self.user_demo).mark_as_sent()
        except AccessError:
            pass
        else:
            self.fail("Un usuario restringido puede marcar como enviados pagos de un diario con journal security")

    def test_journal_security_2(self):
        self.company_bank_journal.write({"journal_restriction": "total", "user_ids": [(4, self.user_admin.id)]})

        payment = (
            self.env["account.payment"]
            .with_user(self.user_admin)
            .with_company(self.first_company)
            .create({"journal_id": self.company_bank_journal.id})
        )

        try:
            payment.with_user(self.user_demo).read()
        except AccessError:
            # Si da un error de acceso para un usuario restringido el test está ok
            pass
        else:
            self.fail("Un usuario restringido tiene acceso a pagos de un diario con journal security")

        try:
            payment.with_user(self.user_admin).read()
        except AccessError:
            self.fail("Un usuario permitido no tiene acceso a los pagos de un diario con journal security")
