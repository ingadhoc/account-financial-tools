##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    debit_card_days_for_collection = fields.Integer(
        help='This number of days will be added to the date of inbound debit '
        'card payments to get the due date, usefull for cashflow analysis'
    )
    credit_card_days_for_collection = fields.Integer(
        help='This number of days will be added to the date of inbound credit '
        'card payments to get the due date, usefull for cashflow analysis'
    )
    acquirer_ids = fields.One2many(
        'payment.acquirer',
        'journal_id',
        'Acquirers',
        help='Acquirer that use this journal to register online payments '
        'journal entries',
    )
    mail_template_id = fields.Many2one(
        'mail.template',
        'Email Template',
        domain=[('model', '=', 'account.move')],
        help="If set an email will be sent to the customer after the invoices"
        " related to this journal has been validated.",
    )

    @api.constrains('currency_id')
    def check_currency(self):
        for rec in self.filtered(lambda x: x.currency_id == x.company_id.currency_id):
            raise ValidationError(_(
                'Solo puede utilizar una moneda secundaria distinta a la '
                'moneda de la compañía (%s).' % (rec.company_id.currency_id.name)))

    def copy(self, default=None):
        rec = super(AccountJournal, self).copy(default=default)
        if rec.type in ('bank', 'cash'):
            default_account = (
                default.get('default_debit_account_id') or
                default.get('default_credit_account_id')) if default else False
            if not default_account:
                company = self.company_id
                account_vals = self._prepare_liquidity_account(
                    rec.name,
                    company,
                    rec.currency_id.id,
                    rec.type)
                default_account = self.env['account.account'].create(
                    account_vals)
                rec.write({
                    'default_debit_account_id': default_account.id,
                    'default_credit_account_id': default_account.id,
                })
        return rec

    def write(self, vals):
        """ We need to allow to change to False the value for restricted for hash for the journal when this value is setted.
        """
        if 'restrict_mode_hash_table' in vals and not vals.get('restrict_mode_hash_table'):
            restrict_mode_hash_table = vals.get('restrict_mode_hash_table')
            vals.pop('restrict_mode_hash_table')
            res = super().write(vals)
            self._write({'restrict_mode_hash_table': restrict_mode_hash_table})
            return res
        return super().write(vals)
