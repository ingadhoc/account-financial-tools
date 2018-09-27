##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    journal_id = fields.Many2one(
        auto_join=True,
    )
