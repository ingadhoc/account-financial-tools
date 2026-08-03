# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo.addons.account.models.account_payment import AccountPayment
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPaymentMissingJournalEntry(AccountTestInvoicingCommon):
    """Recuperación del pago confirmado que quedó sin asiento contable.

    Odoo genera el asiento del pago sólo como efecto colateral del write del
    ``state`` (``account.payment.write``). Si el pago quedó sin asiento y su
    ``state`` ya no es ``draft``/``in_process``, ``action_post`` no escribe nada
    y el asiento no se regenera nunca: el pago queda confirmado sin asiento y no
    hay forma de recuperarlo desde la interfaz.

    Se da con diarios que liquidan contra cuentas ``outstanding`` (las que no son
    ``asset_cash``): sin asiento el pago no tiene residual, ``_compute_state`` lo
    marca ``paid``, y entonces ninguno de los dos ``filtered()`` de
    ``action_post`` lo alcanza. Con cuenta de banco/efectivo no pasa, porque el
    primer ``filtered()`` escribe ``paid`` y ese write sí genera el asiento.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data["default_journal_bank"]
        # El escenario necesita que el método de pago liquide contra una cuenta puente
        # (outstanding receipts) y no contra la de banco/efectivo. AccountTestInvoicingCommon
        # ya deja inbound_payment_method_line configurada así.
        cls.payment_method_line = cls.inbound_payment_method_line

    def _create_posted_payment(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 100.0,
                "journal_id": self.journal.id,
                "payment_method_line_id": self.payment_method_line.id,
            }
        )
        payment.action_post()
        self.assertTrue(payment.move_id, "El pago se debe crear con su asiento contable.")
        self.assertTrue(payment.outstanding_account_id)
        self.assertNotEqual(
            payment.outstanding_account_id.account_type,
            "asset_cash",
            "El escenario requiere una cuenta puente que no sea de efectivo.",
        )
        return payment

    def _orphan_payment(self, payment, state):
        """Deja al pago sin asiento y en ``state``, como quedó en la base del cliente.

        El estado se fuerza por SQL porque no hay forma de armarlo por ORM: escribir el
        ``state`` dispara el ``write`` de ``account.payment``, que es justamente el que
        genera el asiento. El borrado del asiento se hace por ORM, con el pago en
        ``draft``, para no dejar basura colgando y para no depender del constraint
        ``_check_move_id``: con el pago confirmado ese constraint salta o no según cuándo
        se flushee el recompute de ``state`` (en una instalación completa el borrado pasa
        derecho, que es justamente cómo el pago del cliente llegó a quedar sin asiento).
        """
        move = payment.move_id
        self._force_state(payment, "draft")
        move.button_draft()
        move.with_context(force_delete=True).unlink()
        self.assertFalse(payment.move_id, "El asiento del pago debe quedar borrado.")
        self._force_state(payment, state)

    def _force_state(self, payment, state):
        self.env.cr.execute("UPDATE account_payment SET state = %s WHERE id = %s", [state, payment.id])
        payment.invalidate_recordset(["state"])
        self.assertEqual(payment.state, state)

    def test_action_post_regenerates_journal_entry_on_paid_payment(self):
        payment = self._create_posted_payment()
        self._orphan_payment(payment, "paid")

        payment.action_post()

        self.assertTrue(payment.move_id, "action_post debe regenerar el asiento del pago en paid.")
        self.assertEqual(payment.move_id.state, "posted")
        self.assertEqual(
            payment.move_id.line_ids.filtered(lambda line: line.account_id == payment.outstanding_account_id).balance,
            100.0,
        )

    def test_action_post_regenerates_journal_entry_on_in_process_payment(self):
        """El pago en ``in_process`` lo cubre el write de core, pero el resultado debe ser el mismo."""
        payment = self._create_posted_payment()
        self._orphan_payment(payment, "in_process")

        payment.action_post()

        self.assertTrue(payment.move_id, "action_post debe regenerar el asiento del pago en in_process.")
        self.assertEqual(payment.move_id.state, "posted")

    def test_journal_entry_is_regenerated_before_the_rest_of_action_post(self):
        """El asiento se regenera ANTES del resto de la cadena de ``action_post``.

        Lo que corre después trabaja sobre el asiento del pago: en la instalación completa
        ``account_payment_pro._reconcile_after_post`` lo reconcilia contra la deuda leyendo
        ``move_id.line_ids``. Si el asiento se regenerara al final, ese paso no encuentra
        nada y el pago queda con asiento nuevo pero desconciliado de la factura que saldaba
        (con cuenta de efectivo no se ve, porque ahí el asiento se genera dentro del core).
        """
        payment = self._create_posted_payment()
        self._orphan_payment(payment, "paid")
        moves_seen = []
        core_action_post = AccountPayment.action_post

        def spy(payments):
            moves_seen.append(payments.move_id)
            return core_action_post(payments)

        with patch.object(AccountPayment, "action_post", spy):
            payment.action_post()

        self.assertTrue(moves_seen, "El resto de la cadena de action_post no llegó a correr.")
        self.assertEqual(
            moves_seen[0],
            payment.move_id,
            "El asiento ya debe existir cuando corre el resto de action_post.",
        )

    def test_regenerated_journal_entry_keeps_the_payment_date(self):
        """El asiento regenerado se fecha como el pago, no el día en que se repostea."""
        payment = self._create_posted_payment()
        payment.date = "2026-07-01"
        self._orphan_payment(payment, "paid")

        payment.action_post()

        self.assertEqual(payment.move_id.date, payment.date)

    def test_action_post_does_not_generate_journal_entry_on_canceled_payment(self):
        """Un pago cancelado y sin asiento no debe revivir con un asiento nuevo."""
        payment = self._create_posted_payment()
        self._orphan_payment(payment, "canceled")

        payment.action_post()

        self.assertFalse(payment.move_id, "Un pago cancelado no debe generar un asiento nuevo.")
