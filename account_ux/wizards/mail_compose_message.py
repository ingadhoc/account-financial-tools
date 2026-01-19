from odoo import models


class MailComposer(models.TransientModel):
    _inherit = "mail.compose.message"

    def _action_send_mail(self, auto_commit=False):
        result_mails_su, result_messages = super()._action_send_mail(auto_commit=auto_commit)

        for wizard in self:
            res_ids = wizard._evaluate_res_ids()

            if wizard.model == "account.payment":
                self.env["account.payment"].browse(res_ids).write({"is_sent": True})

        return result_mails_su, result_messages
