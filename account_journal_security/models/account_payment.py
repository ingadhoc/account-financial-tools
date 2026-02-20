from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    journal_id = fields.Many2one(
        context={"journal_security": True},
    )
