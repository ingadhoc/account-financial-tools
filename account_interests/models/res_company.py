##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    interest_ids = fields.One2many(
        "res.company.interest",
        "company_id",
        "Interest",
    )
