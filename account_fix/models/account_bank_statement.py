# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountBankStatement(models.Model):

    _inherit = "account.bank.statement"

    journal_type = fields.Selection(readonly=True)
