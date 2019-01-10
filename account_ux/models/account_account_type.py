from odoo import fields, models


class AccountAccountType(models.Model):
    _inherit = "account.account.type"

    analytic_tag_required = fields.Boolean(
        string='Analytic tag required?',
        help="If True, then analytic tags will be required when posting "
        "journal entries with this type of account.",
    )
