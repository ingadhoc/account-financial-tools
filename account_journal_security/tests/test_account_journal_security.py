import odoo.tests.common as common
from odoo import fields
from odoo.exceptions import AccessError


class TestAccountJournalSecurity(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.first_company = self.env["res.company"].search([], limit=1)
        self.company_bank_journal = self.env["account.journal"].search(
            [("company_id", "=", self.first_company.id), ("type", "=", "bank")], limit=1
        )

        self.user_admin = self.env.ref("base.default_user")
        self.user_admin.write({"company_ids": [(4, self.first_company.id)]})
        self.user_demo = self.env.ref("base.user_demo")

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
