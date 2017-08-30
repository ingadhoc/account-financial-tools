# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    active = fields.Boolean(
        'Active',
        default=True
    )
