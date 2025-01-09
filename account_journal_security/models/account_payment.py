from odoo import models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('payment_type')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        available_journals = self.available_journal_ids
        journals_admited_for_user = self.env.user.modification_journal_ids.ids

        for pay in self:
            available_journals -= available_journals.filtered(
                lambda x: x.modification_user_ids and x.id not in journals_admited_for_user)
            pay.available_journal_ids = available_journals
