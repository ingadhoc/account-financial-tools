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

    def _check_payment_state(self):
        if not self.env.context.get("force_delete") and any(m.state not in ("draft", "canceled") for m in self):
            raise UserError(_("You cannot delete this payment, you should set it back to draft first."))

    def unlink(self):
        # Checked before super(): core unlinks the journal entry first, and that trips
        # _check_move_id with a misleading message before any ondelete method runs.
        # Module uninstall passes force_delete, so it is not blocked.
        self._check_payment_state()
        return super().unlink()

    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        for pay in self:
            if not pay.available_journal_ids:
                raise UserError(
                    _("No journals available for company %s and payment type %s.")
                    % (pay.company_id.name, dict(pay._fields["payment_type"].selection).get(pay.payment_type))
                )

    def action_post(self):
        # Odoo genera el asiento del pago sólo como efecto colateral del write del state
        # (account/models/account_payment.py::write). Si al pago le borraron el asiento a mano y su
        # state ya no es draft/paid, action_post no escribe nada y el asiento no se regenera nunca:
        # al borrar el asiento el pago queda sin residual y _compute_state lo marca reconciled, que
        # ningún filtered() de action_post alcanza. Lo forzamos acá.
        # Va ANTES del super() a propósito: lo que corre después trabaja sobre el asiento del pago
        # —account_payment_pro._reconcile_after_post lo reconcilia contra la deuda—, así que
        # regenerarlo al final deja el pago con asiento nuevo pero desconciliado de la factura que
        # saldaba.
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
        return super().action_post()
