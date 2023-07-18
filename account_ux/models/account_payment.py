from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        """ Avoid error when confirming a transfer that if duplicated from another one that is on draft state. The transfer is from a cash journal to another cash journal. """
        for line in self.line_ids.filtered(lambda x: not x.company_currency_id):
            line.company_currency_id = line.company_id.currency_id
        return super().action_post()
