##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def compute_reconciliation_status(self):
        return self._compute_reconciliation_status()
