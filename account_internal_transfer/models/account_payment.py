from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_internal_transfer = fields.Boolean(string="Internal Transfer",
        readonly=False, store=True,
        tracking=True,
        compute="_compute_is_internal_transfer")


    @api.depends('partner_id', 'journal_id', 'destination_journal_id')
    def _compute_is_internal_transfer(self):
        for payment in self:
            payment.is_internal_transfer = (payment.partner_id \
                                           and payment.partner_id == payment.journal_id.company_id.partner_id \
                                           and payment.destination_journal_id) or not payment.partner_id

        if self._context.get('is_internal_transfer_menu'):
            self.is_internal_transfer = True
