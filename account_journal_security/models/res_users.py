##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class Users(models.Model):

    _inherit = 'res.users'

    journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_users',
        'user_id',
        'journal_id',
        'Restricted Journals (TOTAL)',
        context={'active_test': False},
    )

    modification_journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_modification_users',
        'user_id',
        'journal_id',
        'Modification Journals',
        context={'active_test': False},
    )
