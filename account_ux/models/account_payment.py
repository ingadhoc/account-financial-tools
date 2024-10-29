from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # campo a ser extendido y mostrar un nombre detemrinado en las lineas de
    # pago de un payment group o donde se desee (por ej. con cheque, retención,
    # etc)
    payment_method_description = fields.Char(
        compute='_compute_payment_method_description',
        string='Payment Method Desc.',
    )

    @api.depends('payment_method_id')
    def _compute_payment_method_description(self):
        for rec in self:
            rec.payment_method_description = rec.payment_method_id.display_name

    @api.onchange('available_journal_ids')
    def _onchange_available_journal_ids(self):
        """ Fix the use case where a journal only suitable for one kind of operation (lets said inbound) is selected
        and then the user selects "outbound" type, the journals remains selected."""
        if not self.journal_id or self.journal_id not in self.available_journal_ids._origin:
            self.journal_id = self.available_journal_ids._origin[:1]

    @api.depends('invoice_ids.payment_state', 'move_id.line_ids.amount_residual')
    def _compute_state(self):
        super()._compute_state()
        for payment in self:
            if (
                not self.env.context.get('skip_payment_state_computation') and
                payment.journal_id.type in ('bank', 'cash') and
                payment.outstanding_account_id and
                len(payment.move_id.line_ids._reconciled_lines()) > 1
            ):
                payment.state = 'paid'
