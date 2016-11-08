# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    helper_account_id = fields.Many2one(
        'account.account',
        domain=[('deprecated', '=', False), ('reconcile', '=', False)],
        string="Helper Counterpart Account",
        help="Counterpart account on Journal Entries helper"
    )
