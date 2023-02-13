from odoo import models


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    def get_fiscal_position(self, partner_id, delivery_id=None):
        PartnerObj = self.env['res.partner']
        partner = PartnerObj.browse(partner_id)
        delivery = PartnerObj.browse(delivery_id) if delivery_id else None
        return super(AccountFiscalPosition, self)._get_fiscal_position(partner, delivery=delivery)
