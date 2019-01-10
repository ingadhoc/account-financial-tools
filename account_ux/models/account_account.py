##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    analytic_tag_required = fields.Selection([
        ('by_account_type', 'Defined by account type'),
        ('required', 'Required'),
        ('optional', 'Optional'),
    ],
        string='Analytic tag required?',
        default='by_account_type',
        required=True,
        help="Choose if you want analytic tags to be required when posting "
        "journal entries with this account. If you select:"
        "* Defined by account type: it will be required or not regarding the"
        " value of 'Analytic tag required?' on the account type"
        "* Required: it will be required, no matter the value on the account "
        "type"
        "* Optional: it won't be required, no matter the value on the account "
        "type",
    )

    @api.constrains('currency_id')
    def check_currency(self):
        for rec in self.filtered(lambda x: x.currency_id ==
                                 x.company_id.currency_id):
            raise ValidationError(_(
                'Solo puede utilizar una moneda secundaria distinta a la '
                'moneda de la compañía (%s).' % (
                    rec.company_id.currency_id.name)))
