# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models


class Users(models.Model):
    _inherit = 'res.users'

    journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_users',
        'user_id',
        'journal_id',
        'Restricted Journals',
        help='This journals and the information related to it will'
        ' be only visible for users where you specify that they can '
        'see them setting this same field.')
