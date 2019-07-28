##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountGroup(models.Model):
    _inherit = 'account.group'

    child_ids = fields.One2many(
        'account.group',
        'parent_id',
        auto_join=True,
    )
