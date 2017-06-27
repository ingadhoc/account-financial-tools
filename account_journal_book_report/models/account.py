# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import fields, models
import logging

_logger = logging.getLogger(__name__)


class AccountJournalBookGroup(models.Model):
    _name = 'account.journal.book.group'

    name = fields.Char(
        required=True)


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    book_group_id = fields.Many2one(
        'account.journal.book.group',
        string='Book Group',
    )
