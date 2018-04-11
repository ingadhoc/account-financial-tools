##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountMoveLine(models.Model):

    _inherit = "account.move.line"

    company_id = fields.Many2one(readonly=True)
