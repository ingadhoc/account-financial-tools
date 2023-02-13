from odoo import models


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    def get_fiscal_position(self, partner, delivery=None):
        return super(AccountFiscalPosition, self)._get_fiscal_position(partner, delivery=delivery)
