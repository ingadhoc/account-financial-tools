##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountPaymentTerm(models.Model):
    _inherit = ["account.payment.term", "branch.debt.read.mixin"]
