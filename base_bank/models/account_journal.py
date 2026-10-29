from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    bank_id = fields.Many2one(related="bank_account_id.bank_id", readonly=False)
