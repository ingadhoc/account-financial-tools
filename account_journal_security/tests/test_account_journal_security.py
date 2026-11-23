import odoo.tests.common as common
from odoo import fields
from odoo.exceptions import AccessError, ValidationError


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

    def test_journal_security_total_varios_usuarios_habilitados(self):
        """Espejo de test_journal_security_varios_usuarios_habilitados para journal_restriction='total':
        con DOS o mas usuarios en "Totalmente restricto a", cada uno debe seguir viendo el diario
        al crear una OP o un recibo, y el resto no.
        """
        user_allowed_1 = self._create_account_user("journal_security_total_allowed_1")
        user_allowed_2 = self._create_account_user("journal_security_total_allowed_2")
        user_restricted = self._create_account_user("journal_security_total_restricted")

        self.company_bank_journal.write(
            {
                "journal_restriction": "total",
                "user_ids": [(6, 0, [user_allowed_1.id, user_allowed_2.id])],
            }
        )

        for user in (user_allowed_1, user_allowed_2):
            self.assertIn(
                self.company_bank_journal,
                self._search_journal_for_payment(user),
                "Un usuario habilitado a un diario totalmente restringido no lo ve al registrar un pago "
                "cuando hay mas de un usuario habilitado",
            )

        self.assertNotIn(
            self.company_bank_journal,
            self._search_journal_for_payment(user_restricted),
            "Un usuario NO habilitado ve un diario totalmente restringido al registrar un pago",
        )

    def test_journal_security_default_journal_respects_restriction(self):
        """Cuando el ORM elige el diario default (search con limit=1, por ejemplo al crear un
        account.payment sin especificar journal_id): un usuario sin ningun permiso sobre el
        diario restringido no debe recibirlo como default, y el usuario habilitado a modificarlo
        SI debe poder recibir su propio diario restringido como default (aunque la restriccion
        sea de tipo 'modification', que no bloquea la lectura via ir.rule).
        """
        self.company_bank_journal.write(
            {"journal_restriction": "modification", "modification_user_ids": [(4, self.user_admin.id)]}
        )
        unrestricted_bank_journal = self.env["account.journal"].create(
            {
                "name": "Banco sin restriccion",
                "code": "BSR",
                "type": "bank",
                "company_id": self.first_company.id,
            }
        )

        with self.subTest("un usuario sin permiso no recibe el diario restringido como default"):
            default_for_demo = (
                self.env["account.journal"]
                .with_user(self.user_demo)
                .with_company(self.first_company)
                .search([("type", "=", "bank")], limit=1)
            )
            self.assertEqual(
                default_for_demo,
                unrestricted_bank_journal,
                "El diario default (limit=1) para un usuario sin permiso no es el diario sin restriccion",
            )

        with self.subTest("el usuario habilitado puede recibir su propio diario restringido como default"):
            default_for_admin = (
                self.env["account.journal"]
                .with_user(self.user_admin)
                .with_company(self.first_company)
                .search([("id", "=", self.company_bank_journal.id)], limit=1)
            )
            self.assertEqual(
                default_for_admin,
                self.company_bank_journal,
                "El usuario habilitado a modificar el diario no lo recibe como default (limit=1)",
            )

    def test_payment_register_excludes_restricted_journals(self):
        """Verifica el estado final correcto (ticket ingadhoc/account-financial-tools#998):
        el wizard de pago masivo (account.payment.register) no debe dejar que un diario
        totalmente restringido a otro usuario aparezca en available_journal_ids del batch.

        NO verificado como regresion: revirtiendo el fix (sudo(False) + journal_security=True
        en wizards/account_payment_register.py) este test sigue en verde. Confirme con logging
        que journal_id/available_journal_ids se computan en dos pasadas (NewId elevado a sudo,
        luego post-insert con el usuario real) y la segunda pasada pisa el leak de la primera
        antes de que este test pueda observarlo. El fix puede seguir siendo necesario para un
        escenario (edit_mode u otra version de Odoo) que no logre reproducir aca.
        """
        self.company_bank_journal.write({"journal_restriction": "total", "user_ids": [(4, self.user_admin.id)]})
        partner_a = self.env["res.partner"].create({"name": "Journal Security Partner A"})
        partner_b = self.env["res.partner"].create({"name": "Journal Security Partner B"})
        product = self.env.ref("product.product_product_16")
        invoices = self.env["account.move"]
        for partner in (partner_a, partner_b):
            invoice = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "company_id": self.first_company.id,
                    "invoice_line_ids": [(0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 100})],
                }
            )
            invoices |= invoice
        invoices.action_post()

        wizard_restricted = (
            self.env["account.payment.register"]
            .with_user(self.user_demo)
            .with_company(self.first_company)
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create({})
        )
        self.assertNotIn(
            self.company_bank_journal,
            wizard_restricted.available_journal_ids,
            "El pago masivo ofrece un diario totalmente restringido a otro usuario",
        )

        wizard_allowed = (
            self.env["account.payment.register"]
            .with_user(self.user_admin)
            .with_company(self.first_company)
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create({})
        )
        self.assertIn(
            self.company_bank_journal,
            wizard_allowed.available_journal_ids,
            "El pago masivo no ofrece el diario a un usuario habilitado",
        )

    def test_journal_restriction_self_inclusion_constraint(self):
        """Un usuario no puede restringir un diario a una lista de usuarios que no lo incluya a si
        mismo (se quedaria sin ver el diario), salvo que sea el superusuario.
        """
        other_user = self._create_account_user("journal_security_other")

        with self.subTest("un usuario no puede restringir un diario a una lista que no lo incluye"):
            with self.assertRaises(ValidationError):
                self.company_bank_journal.with_user(self.user_admin).write(
                    {"journal_restriction": "total", "user_ids": [(6, 0, [other_user.id])]}
                )

        with self.subTest("el superusuario puede saltear la auto-inclusion"):
            # con self.env por default (superusuario) no hace falta incluirse a si mismo
            self.company_bank_journal.write({"journal_restriction": "total", "user_ids": [(6, 0, [other_user.id])]})
            self.assertEqual(self.company_bank_journal.user_ids, other_user)

    def test_journal_restriction_onchange(self):
        """El onchange de journal_restriction migra/limpia los m2m para que nunca convivan
        user_ids y modification_user_ids al guardar desde la UI.
        """
        with self.subTest("total -> modification copia user_ids a modification_user_ids y vacia user_ids"):
            journal = self.env["account.journal"].new(
                {"name": "Test Journal", "type": "bank", "user_ids": [(6, 0, [self.user_admin.id])]}
            )
            journal.journal_restriction = "modification"
            journal.unset_modification_user_ids()
            self.assertEqual(journal.modification_user_ids.ids, [self.user_admin.id])
            self.assertFalse(journal.user_ids)

        with self.subTest("modification -> total copia modification_user_ids a user_ids y vacia el otro"):
            journal = self.env["account.journal"].new(
                {"name": "Test Journal", "type": "bank", "modification_user_ids": [(6, 0, [self.user_admin.id])]}
            )
            journal.journal_restriction = "total"
            journal.unset_modification_user_ids()
            self.assertEqual(journal.user_ids.ids, [self.user_admin.id])
            self.assertFalse(journal.modification_user_ids)

        with self.subTest("ninguna limpia ambos m2m"):
            journal = self.env["account.journal"].new(
                {"name": "Test Journal", "type": "bank", "user_ids": [(6, 0, [self.user_admin.id])]}
            )
            journal.journal_restriction = "none"
            journal.unset_modification_user_ids()
            self.assertFalse(journal.user_ids)
            self.assertFalse(journal.modification_user_ids)

    def test_journal_security_modification_move_line_write_allowed_create_blocked(self):
        """journal_security_mod_rule_account_move_line tiene perm_write=False a proposito
        (commit 0c6e1cd8, 2019: "allow write for reconciliations") para que cualquiera pueda
        conciliar apuntes existentes de un diario con restriccion de modificacion, aunque no
        este en modification_user_ids. perm_create no esta eximido: crear una linea nueva en
        ese diario sigue bloqueado a los usuarios habilitados. Se usa un asiento en borrador
        (no confirmado) para aislar el control de acceso de las validaciones de negocio de un
        asiento posteado.
        """
        self.company_bank_journal.write(
            {"journal_restriction": "modification", "modification_user_ids": [(4, self.user_admin.id)]}
        )
        receivable_account = self.env["account.account"].search([("account_type", "=", "asset_receivable")], limit=1)
        payable_account = self.env["account.account"].search([("account_type", "=", "liability_payable")], limit=1)
        move = (
            self.env["account.move"]
            .with_user(self.user_admin)
            .with_company(self.first_company)
            .create(
                {
                    "journal_id": self.company_bank_journal.id,
                    "line_ids": [
                        (0, 0, {"name": "debe", "account_id": receivable_account.id, "debit": 100, "credit": 0}),
                        (0, 0, {"name": "haber", "account_id": payable_account.id, "debit": 0, "credit": 100}),
                    ],
                }
            )
        )
        move_line = move.line_ids[:1]

        with self.subTest("un usuario no habilitado puede escribir (conciliar) una linea existente"):
            try:
                move_line.with_user(self.user_demo).write({"name": "conciliado"})
            except AccessError:
                self.fail(
                    "Un usuario no habilitado a modificar el diario no puede escribir un apunte "
                    "existente; la regla deberia eximir el write para permitir conciliaciones"
                )

        with self.subTest("un usuario no habilitado no puede crear una linea nueva en ese diario"):
            with self.assertRaises(AccessError):
                self.env["account.move.line"].with_user(self.user_demo).create(
                    {"move_id": move.id, "name": "linea nueva", "account_id": receivable_account.id}
                )
