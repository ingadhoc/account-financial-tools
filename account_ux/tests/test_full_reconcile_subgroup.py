# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFullReconcileSubgroup(AccountTestInvoicingCommon):
    """Número de conciliación para la deuda que sí cerró dentro de un lote parcial.

    Si se cobra o paga seleccionando más deudas de las que el importe cubre, odoo no
    numera ninguna: las que cerraron quedan con marca de conciliación parcial en el
    mayor. Los saldos son correctos, lo que falta es la marca. Ticket 123989.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.receivable_account = cls.company_data["default_account_receivable"]

    def _create_invoice(self, amount):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-01-01",
                "date": "2026-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "line",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _receivable_line(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.account_id == self.receivable_account)

    def _create_payment(self, amount):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": amount,
                "date": "2026-01-02",
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        payment.action_post()
        return payment.move_id.line_ids.filtered(lambda line: line.account_id == self.receivable_account)

    def test_partial_batch_creates_full_for_closed_subgroup(self):
        """El lote deja una deuda abierta: la que cerró igual se numera."""
        invoice_covered = self._create_invoice(100.0)
        invoice_open = self._create_invoice(100.0)
        covered_line = self._receivable_line(invoice_covered)
        open_line = self._receivable_line(invoice_open)
        payment_line = self._create_payment(100.0)

        (payment_line + covered_line + open_line).reconcile()

        self.assertTrue(
            self.env.company.currency_id.is_zero(covered_line.amount_residual),
            "La primera deuda tiene que quedar cancelada.",
        )
        self.assertFalse(
            self.env.company.currency_id.is_zero(open_line.amount_residual),
            "La segunda deuda tiene que quedar abierta.",
        )
        self.assertTrue(
            covered_line.full_reconcile_id,
            "La deuda que cerró tiene que tener número de conciliación.",
        )
        self.assertEqual(
            covered_line.full_reconcile_id,
            payment_line.full_reconcile_id,
            "El pago y la deuda que canceló comparten el número.",
        )
        self.assertFalse(
            open_line.full_reconcile_id,
            "La deuda abierta no lleva número.",
        )
        self.assertNotIn(
            open_line,
            covered_line.full_reconcile_id.reconciled_line_ids,
            "El número sólo abarca lo que cerró.",
        )

    def test_partial_batch_from_payment_register(self):
        """Mismo caso desde el wizard de registro de pagos."""
        invoice_covered = self._create_invoice(100.0)
        invoice_open = self._create_invoice(100.0)
        invoices = invoice_covered + invoice_open

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create(
                {
                    "amount": 100.0,
                    "payment_date": "2026-01-02",
                    "group_payment": True,
                    "journal_id": self.company_data["default_journal_bank"].id,
                }
            )
        )
        wizard._create_payments()

        covered_line = self._receivable_line(invoice_covered)
        open_line = self._receivable_line(invoice_open)
        self.assertTrue(
            self.env.company.currency_id.is_zero(covered_line.amount_residual),
            "El cobro cancela la primera factura.",
        )
        self.assertFalse(
            self.env.company.currency_id.is_zero(open_line.amount_residual),
            "La segunda factura tiene que quedar abierta.",
        )
        self.assertTrue(
            covered_line.full_reconcile_id,
            "La factura cancelada tiene que tener número.",
        )
        self.assertFalse(open_line.full_reconcile_id)

    def test_full_batch_still_creates_single_full(self):
        """Control: el lote que cierra entero sigue dando un solo número."""
        invoice_1 = self._create_invoice(100.0)
        invoice_2 = self._create_invoice(100.0)
        line_1 = self._receivable_line(invoice_1)
        line_2 = self._receivable_line(invoice_2)
        payment_line = self._create_payment(200.0)

        (payment_line + line_1 + line_2).reconcile()

        fulls = (payment_line + line_1 + line_2).full_reconcile_id
        self.assertEqual(len(fulls), 1, "Un lote que cierra entero da un solo número.")
        self.assertEqual(
            fulls.reconciled_line_ids,
            payment_line + line_1 + line_2,
            "El número abarca las tres líneas.",
        )

    def test_partially_paid_invoice_gets_no_full(self):
        """Control: un pago a cuenta no numera nada."""
        invoice = self._create_invoice(100.0)
        invoice_line = self._receivable_line(invoice)
        payment_line = self._create_payment(40.0)

        (payment_line + invoice_line).reconcile()

        self.assertFalse(
            invoice_line.full_reconcile_id,
            "La deuda sigue abierta: no lleva número.",
        )
        self.assertFalse(
            payment_line.full_reconcile_id,
            "El pago se consumió pero la deuda no cerró.",
        )

    def test_pending_exchange_difference_gets_no_full(self):
        """Control: si falta saldar la moneda secundaria, el caso queda para el core."""
        foreign = self.setup_other_currency("EUR")
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2017-01-01",
                "date": "2017-01-01",
                "currency_id": foreign.id,
                "invoice_line_ids": [
                    Command.create({"name": "line", "quantity": 1, "price_unit": 120.0, "tax_ids": []})
                ],
            }
        )
        invoice.action_post()
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 180.0,
                "currency_id": foreign.id,
                "date": "2016-01-01",
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        payment.action_post()
        invoice_line = self._receivable_line(invoice)
        payment_line = payment.move_id.line_ids.filtered(lambda line: line.account_id == self.receivable_account)

        # Sin el asiento por diferencia de cambio, el saldo cierra en pesos pero no en
        # la moneda del comprobante.
        lines = payment_line + invoice_line
        lines.with_context(no_exchange_difference=True).reconcile()

        self.assertTrue(
            self.env.company.currency_id.is_zero(invoice_line.amount_residual),
            "El escenario necesita que el saldo en moneda de compañía cierre.",
        )
        self.assertFalse(
            all(foreign.is_zero(line.amount_residual_currency) for line in lines),
            "El escenario necesita saldo pendiente en la moneda del comprobante.",
        )
        self.assertFalse(
            lines.full_reconcile_id,
            "Con moneda secundaria sin saldar no numeramos: es del core.",
        )
