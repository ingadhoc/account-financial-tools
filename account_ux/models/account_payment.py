from odoo import _, api, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.onchange("available_journal_ids")
    def _onchange_available_journal_ids(self):
        """Fix the use case where a journal only suitable for one kind of operation (lets said inbound) is selected
        and then the user selects "outbound" type, the journals remains selected."""
        if not self.journal_id or self.journal_id not in self.available_journal_ids._origin:
            self.journal_id = self.available_journal_ids._origin[:1]

    @api.depends("invoice_ids.payment_state", "move_id.line_ids.amount_residual")
    def _compute_state(self):
        super()._compute_state()
        for payment in self:
            if (
                not self.env.context.get("skip_payment_state_computation")
                and payment.journal_id.type in ("bank", "cash", "credit")
                and payment.state == "in_process"
                and payment.outstanding_account_id
                and len(payment.move_id.line_ids._reconciled_lines()) > 1
                and not payment.payment_method_line_id.payment_account_id.reconcile
            ):
                payment.action_post()

    @api.ondelete(at_uninstall=False)
    def _check_payment_state(self):
        if not self._context.get("force_delete") and any(m.state not in ("draft", "canceled") for m in self):
            raise UserError(_("You cannot delete this payment, you should set it back to draft first."))

    def action_post(self):
        # Odoo genera el asiento del pago sólo como efecto colateral del write del state
        # (account/models/account_payment.py::write). Si al pago le borraron el asiento a mano y su
        # state ya no es draft/in_process, action_post no escribe nada y el asiento no se regenera
        # nunca. Pasa con diarios que usan cuentas outstanding: al borrar el asiento el pago queda
        # sin residual y _compute_state lo marca paid, entonces ninguno de los dos filtered() de
        # action_post lo alcanza. Lo forzamos acá.
        # Va ANTES del super() a propósito: lo que corre después trabaja sobre el asiento del pago
        # —account_payment_pro._reconcile_after_post lo reconcilia contra la deuda—, así que
        # regenerarlo al final deja el pago con asiento nuevo pero desconciliado de la factura que
        # saldaba. Con cuenta de efectivo no se notaba porque ahí el asiento se regenera dentro del
        # super(): el core fuerza state='paid' para asset_cash y ese write ya lo genera.
        missing_move = self.filtered(
            lambda pay: (
                not pay.move_id and pay.outstanding_account_id and pay.state not in ("draft", "canceled", "rejected")
            )
        )
        if missing_move:
            missing_move._generate_journal_entry()
            for payment in missing_move:
                payment.move_id.date = payment.date
            missing_move.move_id.filtered(lambda move: move.state == "draft").action_post()
        super().action_post()
        self.filtered(lambda pay: pay.outstanding_account_id.account_type == "liability_credit_card").state = "paid"
