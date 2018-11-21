##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.constrains('currency_id')
    def check_currency(self):
        for rec in self.filtered(lambda x: x.currency_id ==
                                 x.company_id.currency_id):
            raise ValidationError(_(
                'Solo puede utilizar una moneda secundaria distinta a la '
                'moneda de la compañía (%s).' % (
                    rec.company_id.currency_id.name)))
