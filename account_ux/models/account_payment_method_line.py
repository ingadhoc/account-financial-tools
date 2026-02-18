from odoo import fields, models


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    shared_to_branches = fields.Boolean(
        related="journal_id.shared_to_branches",
        store=True,
    )
