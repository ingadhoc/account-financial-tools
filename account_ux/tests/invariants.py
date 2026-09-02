##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
"""Batería de invariantes de cobros y pagos.

Verificaciones que toda operación de cobro o pago tiene que cumplir siempre.
Viven acá porque retenciones, motor de importes y cheques dependen de este
módulo: una sola definición de "el asiento está sano", no una copia por suite.

Uso: heredar el mixin y llamar ``assert_payment_invariants`` después de cada
operación, más los asserts puntuales de saldo o estado.

    class TestAlgo(AccountInvariantsMixin, TransactionCase):
        def test_algo(self):
            self.assert_payment_invariants(payment)
            self.assert_payment_state(invoice, "paid")

Qué NO está acá: que el asiento sume cero. El ORM no deja construir uno
descuadrado (lo completa con una línea de relleno si hay impuestos, o lo
rechaza), así que ese assert no tiene forma de ponerse en rojo. Ver
``assert_no_automatic_balancing_line``.

El mixin no lleva flags para saltear invariantes: la excepción se declara en
el test, a la vista.
"""


class AccountInvariantsMixin:
    # ------------------------------------------------------------------
    # invariantes del asiento
    # ------------------------------------------------------------------
    def assert_no_automatic_balancing_line(self, move, msg=""):
        """No hay línea de balanceo automático.

        Se identifica por **nombre** (como Odoo en ``_sync_unbalanced_lines``),
        no por cuenta: ``_get_automatic_balancing_account()`` devuelve la
        default del diario, así que por cuenta cualquier pago de banco/caja
        da positivo siempre.
        """
        balance_name = self.env._("Automatic Balancing Line")
        balancing = move.line_ids.filtered(lambda line: line.name == balance_name)
        self.assertFalse(
            balancing,
            "El asiento %s tiene línea de balanceo automático por %s. %s"
            % (move.name, sum(balancing.mapped("balance")), msg),
        )

    def assert_no_zero_lines(self, move, msg=""):
        """Ninguna línea en cero: un mecanismo que se disparó sin nada que
        hacer (write-off que no correspondía, retención en cero)."""
        zero_lines = move.line_ids.filtered(lambda line: not line.debit and not line.credit)
        self.assertFalse(
            zero_lines,
            "El asiento %s tiene %s línea(s) en cero: %s. %s"
            % (move.name, len(zero_lines), zero_lines.mapped("name"), msg),
        )

    def assert_closes_in_both_currencies(self, move, msg=""):
        """En multimoneda, cierra también en la moneda del comprobante.

        Precondición: vale para asientos cuyas líneas en moneda extranjera se
        cierran entre sí. Un asiento que mezcla una línea en moneda con
        contrapartida en moneda de compañía no cierra por moneda y no tiene
        por qué — el escenario assertea sobre el importe convertido en su
        lugar.
        """
        by_currency = {}
        for line in move.line_ids.filtered(lambda line: line.currency_id != line.company_currency_id):
            by_currency.setdefault(line.currency_id, 0.0)
            by_currency[line.currency_id] += line.amount_currency
        for currency, total in by_currency.items():
            self.assertEqual(
                currency.round(total),
                0.0,
                "El asiento %s no cierra en %s (%s). %s" % (move.name, currency.name, total, msg),
            )

    # ------------------------------------------------------------------
    # invariantes del pago
    # ------------------------------------------------------------------
    def assert_no_open_outstanding(self, payment, msg=""):
        """La cuenta pendiente del pago no queda con saldo sin conciliar,
        salvo que el escenario lo declare (transitoria que no se cerró aún)."""
        pending = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == payment.outstanding_account_id and not line.reconciled
        )
        self.assertFalse(
            pending,
            "El pago %s deja %s apunte(s) sin conciliar en la cuenta pendiente. %s" % (payment.name, len(pending), msg),
        )

    def assert_payment_invariants(self, payment, msg=""):
        """Las invariantes que todo pago tiene que cumplir, en un solo lugar."""
        move = payment.move_id
        self.assert_no_automatic_balancing_line(move, msg)
        self.assert_no_zero_lines(move, msg)
        currencies = move.line_ids.currency_id
        if len(currencies) == 1 and currencies != payment.company_currency_id:
            self.assert_closes_in_both_currencies(move, msg)

    # ------------------------------------------------------------------
    # invariantes del comprobante y del partner
    # ------------------------------------------------------------------
    def assert_payment_state(self, invoice, expected, msg=""):
        """El estado de pago es uno y es el declarado — nunca "pagada o en
        proceso" indistintamente."""
        self.assertEqual(
            invoice.payment_state,
            expected,
            "La factura %s quedó en '%s' y el escenario declara '%s'. %s"
            % (invoice.name, invoice.payment_state, expected, msg),
        )

    def assert_partner_balance(self, partner, expected, account_type="asset_receivable", msg=""):
        """Saldo del partner sobre apuntes publicados.

        Vale solo para partners que creó el test: es un ``search`` sobre
        todos los apuntes del partner en la compañía, y uno de la base
        arrastraría saldo ajeno.
        """
        lines = self.env["account.move.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("company_id", "=", self.env.company.id),
                ("account_id.account_type", "=", account_type),
                ("parent_state", "=", "posted"),
            ]
        )
        balance = self.env.company.currency_id.round(sum(lines.mapped("amount_residual")))
        self.assertEqual(
            balance,
            expected,
            "El partner %s quedó con saldo %s y el escenario declara %s. %s"
            % (partner.display_name, balance, expected, msg),
        )
