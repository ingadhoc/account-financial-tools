# © 2018 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models, _
from odoo.exceptions import ValidationError


class ResCurrencyRate(models.Model):

    _inherit = 'res.currency.rate'

    @api.constrains('company_id')
    def _check_date_rate(self):
        for rec in self.filtered(lambda x: not x.company_id):
            others_with_company = self.search([
                ('name', '<=', rec.name),
                ('currency_id', '=', rec.currency_id.id),
                ('company_id', '!=', False),
            ])
            if others_with_company:
                raise ValidationError(_(
                    'You can not create a rate without company'
                    ' since you already have rates before %s with'
                    ' company set. The rate you want to create will not'
                    ' have any effect, will not be take into account.'
                ) % rec.name)
