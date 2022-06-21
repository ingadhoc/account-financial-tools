from odoo import models, _
from odoo.exceptions import UserError


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        if self._context.get('active_model') == 'account.move':
            domain = [('id', 'in', self._context.get('active_ids', [])), ('state', '=', 'draft')]
        elif self._context.get('active_model') == 'account.journal':
            domain = [('journal_id', '=', self._context.get('active_id')), ('state', '=', 'draft')]
        else:
            raise UserError(_("Missing 'active_model' in context."))

        moves = self.env['account.move'].search(domain).filtered('line_ids')
        try:
            res = super().validate_move()
            moves.with_context(mail_notify_force_send=False).action_send_invoice_mail()
        except Exception as exp:
            # we try to send by email the invoices recently validated
            posted_moves = self.filter_posted_moves(moves)
            posted_moves.with_context(mail_notify_force_send=False).action_send_invoice_mail()
            raise exp

        return res

    def filter_posted_moves(self, moves):
        return moves.filtered(lambda x: x.state == 'posted')
