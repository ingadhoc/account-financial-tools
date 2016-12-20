# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    tax_settlement_detail_id = fields.Many2one(
        'account.tax.settlement.detail',
        'Tax Settlement Detail',
        )
    tax_state = fields.Selection([
        ('to_settle', _('To Settle')),
        ('to_pay', _('To Pay')),
        ('paid', _('Paid')),
        ],
        _('Tax State'),
        compute='_get_tax_state',
        # store=True,
        )
    tax_settlement_move_id = fields.Many2one(
        'account.move',
        'Tax Settlement Move',
        help='Move where this tax has been settled',
        )

    # NOTO. No se porque me da un error esta funcion. Por ahora pusimos
    # restriccion en tax settlement
    # @api.multi
    # def write(self, vals):
    #     """
    #     Check that you are not writing tax_settlement_move_id to a line that
    #     has it already setted
    #     """
    #     if 'tax_settlement_move_id' in vals:
    #         if self.filtered('tax_settlement_move_id'):
    #             raise ValidationError(_(
    #                 'I seams that some lines has been already settled.\n'
    #                 '* Lines: %s') % (
    #                 self.filtered('tax_settlement_move_id').ids))
    #     return super(account_move_line, self).write(vals)

    @api.one
    @api.depends(
        'tax_code_id',
        # 'tax_settlement_move_id',
        'tax_settlement_move_id.payable_residual',
        )
    def _get_tax_state(self):
        if self.tax_code_id:
            tax_state = 'to_settle'
            if self.tax_settlement_move_id:
                tax_state = 'to_pay'
                # if tax_settlement_move_id and move are the same, then
                # we are on the settlement move line
                if self.tax_settlement_move_id == self.move_id:
                    tax_state = False
                elif self.tax_settlement_move_id.payable_residual == 0.0:
                    tax_state = 'paid'
            self.tax_state = tax_state

    @api.multi
    def pay_tax_settlement(self):
        self.ensure_one()
        return self.tax_settlement_move_id.with_context(
            from_settlement=True).create_voucher('payment')

    @api.multi
    def make_tax_settlement(self):
        self.ensure_one()
        if self.tax_settlement_move_id:
            raise ValidationError(_('Line already settled'))
        if not self.tax_code_id:
            raise ValidationError(_(
                'Settlement only alled for journal items with tax code'))

        # get parent tax codes (only parents)
        parent_tax_codes_ids = []
        parent_tax_code = self.tax_code_id
        while parent_tax_code:
            parent_tax_codes_ids.append(parent_tax_code.id)
            parent_tax_code = parent_tax_code.parent_id

        # parent_tax_codes_ids = self.
        journals = self.env['account.journal'].search([
            ('type', '=', 'tax_settlement'),
            ('tax_code_id', 'in', parent_tax_codes_ids),
            ])

        if not journals:
            raise ValidationError(_(
                'No tax settlemnt journal found for tax code %s') % (
                self.tax_code_id.name))
        elif len(journals) != 1:
            raise ValidationError(_(
                'Only one tax settlemnt journal must exist for tax code %s'
                'We have found the journal ids %s') % (
                self.tax_code_id, journals.ids))
        else:
            journal = journals

        # check account payable
        if self.debit < self.credit:
            account = journal.default_debit_account_id
            tax_code = journal.default_debit_tax_code_id
        else:
            account = journal.default_credit_account_id
            tax_code = journal.default_credit_tax_code_id

        # check account type so that we can create a debt
        if account.type != 'payable':
            raise ValidationError(_(
                'You can only pay if tax counterpart use a payable account.'
                'Account id %i' % account.id))

        # get date, period and name
        date = fields.Date.context_today(self)
        period = self.env['account.period'].with_context(
            company_id=self.company_id.id).find(date)[:1]
        name = journal.sequence_id._next()

        move_vals = {
            'ref': name,
            'name': name,
            'period_id': period.id,
            'date': date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            }
        move = self.env['account.move'].create(move_vals)

        # write move id on settled tax move line
        self.tax_settlement_move_id = move.id

        counterpart_line_vals = {
            'move_id': move.id,
            'partner_id': self.partner_id.id,
            'name': self.name,
            'debit': self.credit,
            'credit': self.debit,
            'account_id': self.account_id.id,
            'tax_code_id': self.tax_code_id.id,
            'tax_amount': self.tax_amount,
            'tax_settlement_move_id': move.id,
        }
        move.line_id.create(counterpart_line_vals)

        # TODO ver si ref se completa con el name del journal
        deb_line_vals = {
            'move_id': move.id,
            'partner_id': journal.partner_id.commercial_partner_id.id,
            'name': self.name,
            'debit': self.debit,
            'credit': self.credit,
            'account_id': account.id,
            'tax_code_id': tax_code.id,
            'tax_amount': -1.0 * self.tax_amount,
        }
        move.line_id.create(deb_line_vals)
        return True
