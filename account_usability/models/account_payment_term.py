# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    company_id = fields.Many2one(
        default=False,
        required=False
    )
