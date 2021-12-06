from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    journal_id = fields.Many2one(tracking=True)
    destination_journal_id = fields.Many2one(tracking=True)
    currency_id = fields.Many2one(tracking=True)
