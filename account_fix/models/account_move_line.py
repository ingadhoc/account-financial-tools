# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class AccountMoveLine(models.Model):

    _inherit = "account.move.line"

    company_id = fields.Many2one(readonly=True)
