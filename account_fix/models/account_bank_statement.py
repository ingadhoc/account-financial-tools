# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class AccountBankStatement(models.Model):

    _inherit = "account.bank.statement"

    journal_type = fields.Selection(readonly=True)
