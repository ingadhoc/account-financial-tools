##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .invariants import AccountInvariantsMixin


@tagged("post_install", "-at_install")
class TestAccountInvariants(AccountInvariantsMixin, TransactionCase):
    """Cada invariante probada en los dos sentidos: pasa en verde, falla en
    rojo con la operación que tiene que detectar. La va a llamar toda suite
    de cobros y pagos, así que un error acá las deja a todas sin verificar.

    Arma cuentas/diario/moneda con ``.create()`` en vez de heredar
    ``AccountTestInvoicingCommon``, que en bases OBA con todo instalado se
    corta por ACL de productos de demo.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.receivable = cls._account("TINVR", "Test Receivable", "asset_receivable", reconcile=True)
        cls.expense = cls._account("TINVE", "Test Expense", "expense")
        cls.income = cls._account("TINVI", "Test Income", "income")
        cls.outstanding = cls._account("TINVO", "Test Outstanding Receipts", "asset_current", reconcile=True)
        cls.journal = cls.env["account.journal"].create(
            {"name": "Test Invariants Misc", "code": "TINVJ", "type": "general", "company_id": cls.company.id}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Test Invariants Partner"})
        if not cls.company.account_journal_suspense_account_id:
            cls.company.account_journal_suspense_account_id = cls._account("TINVS", "Test Suspense", "asset_current")
        cls.suspense = cls.company.account_journal_suspense_account_id
        cls.foreign_currency = cls._foreign_currency()
        cls.tax = cls._tax()
        cls.bank_journal, cls.manual_in_line = cls._bank_journal()
        # payment_pro reescribe los importes de todo pago; su propia suite cubre la combinación
        if "use_payment_pro" in cls.env["res.company"]._fields:
            cls.company.use_payment_pro = False

    @classmethod
    def _account(cls, code, name, account_type, reconcile=False):
        return cls.env["account.account"].create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_ids": [Command.set(cls.company.ids)],
            }
        )

    @classmethod
    def _bank_journal(cls):
        """Diario de banco con transitoria propia — es lo que mira
        ``assert_no_open_outstanding``."""
        journal = cls.env["account.journal"].create(
            {"name": "Test Invariants Bank", "code": "TINVB", "type": "bank", "company_id": cls.company.id}
        )
        method = cls.env.ref("account.account_payment_method_manual_in")
        journal.write(
            {
                "inbound_payment_method_line_ids": [
                    Command.create(
                        {"payment_method_id": method.id, "name": "Manual", "payment_account_id": cls.outstanding.id}
                    )
                ]
            }
        )
        line = journal.inbound_payment_method_line_ids.filtered(lambda x: x.payment_account_id == cls.outstanding)[-1]
        return journal, line

    @classmethod
    def _tax(cls):
        """Necesario para provocar la línea de relleno: sin impuestos Odoo
        rechaza el asiento descompensado en vez de completarlo."""
        vals = {
            "name": "Test Invariants Tax",
            "amount_type": "percent",
            "amount": 21.0,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        }
        group = cls.env["account.tax.group"].search([("company_id", "=", cls.company.id)], limit=1)
        if group:
            vals["tax_group_id"] = group.id
        return cls.env["account.tax"].create(vals)

    @classmethod
    def _foreign_currency(cls):
        """Creada, no buscada: qué monedas están activas depende de la base."""
        currency = cls.env["res.currency"].create({"name": "TIV", "symbol": "I$", "rounding": 0.01})
        cls.env["res.currency.rate"].create(
            {
                "name": "2026-01-01",
                "currency_id": currency.id,
                "company_id": cls.company.id,
                "rate": 1 / 2.0,
            }
        )
        return currency

    def _entry(self, lines):
        """Asiento en borrador con las líneas que pide el escenario."""
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "company_id": self.company.id,
                "date": "2026-01-01",
                "line_ids": [Command.create(vals) for vals in lines],
            }
        )

    def _balance(self, move):
        return move.company_currency_id.round(sum(move.line_ids.mapped("balance")))

    def test_a_clean_entry_passes_every_invariant(self):
        """Un asiento sano no dispara ninguna invariante."""
        move = self._entry(
            [
                {"name": "debt", "account_id": self.receivable.id, "debit": 1000.0},
                {"name": "expense", "account_id": self.expense.id, "credit": 1000.0},
            ]
        )
        self.assert_no_automatic_balancing_line(move)
        self.assert_no_zero_lines(move)

    def test_zero_amount_line_is_detected(self):
        """Una línea en cero tiene que hacer fallar la batería."""
        move = self._entry(
            [
                {"name": "debt", "account_id": self.receivable.id, "debit": 1000.0},
                {"name": "expense", "account_id": self.expense.id, "credit": 1000.0},
                {"name": "ajuste vacío", "account_id": self.expense.id, "debit": 0.0, "credit": 0.0},
            ]
        )
        with self.assertRaises(AssertionError):
            self.assert_no_zero_lines(move)

    def test_automatic_balancing_line_is_detected(self):
        """La línea con la que Odoo completa un asiento tiene que fallar.

        La provoca un impuesto que descompensa el asiento, no el test a
        mano: escribirla directo verificaría el propio fixture. La
        cuadratura no es invariante de la batería (no puede ir a rojo); esta sí.
        """
        move = self._entry(
            [
                {"name": "debt", "account_id": self.receivable.id, "debit": 1000.0},
                {
                    "name": "income",
                    "account_id": self.income.id,
                    "credit": 1000.0,
                    "tax_ids": [Command.set(self.tax.ids)],
                },
            ]
        )
        self.assertEqual(self._balance(move), 0.0, "el asiento cierra: es justo lo que lo hace peligroso")
        self.assertTrue(
            move.line_ids.filtered(lambda line: line.name == self.env._("Automatic Balancing Line")),
            "el fixture tiene que haber provocado la línea de relleno de Odoo",
        )
        with self.assertRaises(AssertionError):
            self.assert_no_automatic_balancing_line(move)

    def test_entry_that_does_not_close_in_the_foreign_currency_is_detected(self):
        """Cerrar en moneda de compañía y no en la del comprobante tiene que fallar."""
        move = self._entry(
            [
                {
                    "name": "debt",
                    "account_id": self.receivable.id,
                    "debit": 1000.0,
                    "currency_id": self.foreign_currency.id,
                    "amount_currency": 500.0,
                },
                {
                    "name": "expense",
                    "account_id": self.expense.id,
                    "credit": 1000.0,
                    "currency_id": self.foreign_currency.id,
                    "amount_currency": -450.0,
                },
            ]
        )
        self.assertEqual(self._balance(move), 0.0, "cierra en moneda de compañía")
        with self.assertRaises(AssertionError):
            self.assert_closes_in_both_currencies(move)

    def test_partner_balance_is_measured_on_posted_entries(self):
        """El saldo del partner sale de apuntes publicados, y el assert es exacto."""
        move = self._entry(
            [
                {
                    "name": "debt",
                    "account_id": self.receivable.id,
                    "partner_id": self.partner.id,
                    "debit": 1000.0,
                },
                {"name": "income", "account_id": self.expense.id, "credit": 1000.0},
            ]
        )
        with self.subTest("en borrador el apunte todavía no cuenta"):
            self.assert_partner_balance(self.partner, 0.0)
        with self.subTest("publicado, el saldo es el del apunte"):
            move.action_post()
            self.assert_partner_balance(self.partner, 1000.0)
        with self.subTest("un saldo distinto al declarado hace fallar"):
            with self.assertRaises(AssertionError):
                self.assert_partner_balance(self.partner, 900.0)

    def test_outstanding_and_payment_state_follow_the_collection_chain(self):
        """not_paid → in_payment → paid, con la transitoria en cada paso.

        Camina la cadena porque las dos invariantes distinguen justo los
        pasos intermedios: in_payment no es paid, y una transitoria abierta
        no es error mientras el escenario lo declare.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.context_today(self.env["account.move"]),
                "company_id": self.company.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test invariants line",
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "account_id": self.income.id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": self.manual_in_line.id,
                "company_id": self.company.id,
                "amount": 1000.0,
                "date": fields.Date.context_today(self.env["account.payment"]),
            }
        )
        payment.action_post()

        with self.subTest("pago publicado y sin conciliar: la factura sigue impaga"):
            self.assert_payment_invariants(payment, "cobro contra transitoria")
            self.assert_payment_state(invoice, "not_paid")
            with self.assertRaises(AssertionError):
                self.assert_no_open_outstanding(payment)

        with self.subTest("conciliado con la factura queda en proceso, no pagada"):
            receivable = (invoice.line_ids + payment.move_id.line_ids).filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
            receivable.reconcile()
            self.assert_payment_state(invoice, "in_payment")
            with self.assertRaises(AssertionError):
                self.assert_payment_state(invoice, "paid")
            with self.assertRaises(AssertionError):
                self.assert_no_open_outstanding(payment)

        with self.subTest("cerrada la transitoria contra el banco, la factura queda pagada"):
            bank_entry = self._entry(
                [
                    {"name": "banco", "account_id": self.expense.id, "debit": 1000.0},
                    {"name": "transitoria", "account_id": self.outstanding.id, "credit": 1000.0},
                ]
            )
            bank_entry.action_post()
            outstanding_lines = (bank_entry.line_ids + payment.move_id.line_ids).filtered(
                lambda line: line.account_id == self.outstanding
            )
            outstanding_lines.reconcile()
            self.assert_no_open_outstanding(payment)
            self.assert_payment_state(invoice, "paid")
