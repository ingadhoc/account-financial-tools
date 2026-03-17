from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _compute_available_journal_ids(self):
        super(AccountPayment, self.with_context(journal_security=True))._compute_available_journal_ids()
