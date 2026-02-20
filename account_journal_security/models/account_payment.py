from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        context={"journal_security": True},
    )
