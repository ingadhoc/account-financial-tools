##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    analytic_account_required = fields.Selection([
        ('by_account_type', 'Defined by account type'),
        ('required', 'Required'),
        ('optional', 'Optional'),
    ],
        string='Analytic account required?',
        default='by_account_type',
        required=True,
        help="Choose if you want analytic accounts to be required when posting "
        "journal entries with this account. If you select:"
        "* Defined by account type: it will be required or not regarding the"
        " value of 'Analytic account required?' on the account type"
        "* Required: it will be required, no matter the value on the account "
        "type"
        "* Optional: it won't be required, no matter the value on the account "
        "type",
    )
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

    group_id = fields.Many2one(
        'account.group',
        # we restrict those who do not have childs categories
        domain=[('child_ids', '=', False)],
    )

    @api.constrains('currency_id')
    def check_currency(self):
        for rec in self.filtered(lambda x: x.currency_id == x.company_id.currency_id):
            raise ValidationError(_(
                'Solo puede utilizar una moneda secundaria distinta a la '
                'moneda de la compañía (%s).' % (
                    rec.company_id.currency_id.name)))

    def write(self, vals):
        """ If user sets and account of a liquidity type and previous type was not liquidity and not reconcilable,
        recompute amounts residual because they are used on liquidity accounts
        """
        user_type = self.env['account.account.type'].browse(vals.get('user_type_id'))
        aml_to_recompute = self.env['account.move.line']
        if user_type and user_type.type == 'liquidity':
            accounts_to_re_compute = self.filtered(lambda x: not x.reconcile and x.user_type_id.type != 'liquidity')
            aml_to_recompute = aml_to_recompute.search([('account_id', 'in', accounts_to_re_compute.ids)])
        res = super(AccountAccount, self).write(vals=vals)
        aml_to_recompute._amount_residual()
        return res
