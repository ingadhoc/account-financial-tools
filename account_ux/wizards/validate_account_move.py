from odoo import models


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        """The native flow posts with moves_to_post._post(), which skips our action_post override,
        so invoices confirmed from the list view never sent the journal mail template.

        account_background_post already iterates action_post per move when count_inv is set, so
        this only adds the sending on the native branch; the ones already sent there are skipped
        by action_send_invoice_mail. Moves left in draft by soft posting (future dated) are
        deferred to the native cron by that same method.
        """
        res = super().validate_move()
        self.move_ids.action_send_invoice_mail()
        return res
