# -*- coding: utf-8 -*-
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, api, fields


class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
    )
    reconciled_financial_amount_ = fields.Float(
        compute='_get_reconciled_financial_amount_',
        string='Reconciled Financial Amount',
    )

    @api.one
    @api.depends(
        'line_cr_ids.financial_amount_unreconciled',
        'line_cr_ids.amount_unreconciled',
        'line_dr_ids.financial_amount_unreconciled',
        'line_dr_ids.amount_unreconciled',
    )
    def _get_reconciled_financial_amount_(self):
        # self.financial_amount = sum
        # debit = sum([x.amount for x in self.line_cr_ids])
        # credit = sum([x.amount for x in self.line_dr_ids])
        # for line in self.line_cr_ids:
        #     line_currency = line.move_line_id.currency_id
        #     if line_currency:
        #         line_currency.compute(
        #             line.amount_residual_currency,
        #             line.account_id.company_id.currency_id)
        def get_lines_financial_amount(lines):
            financial_amount = 0.0
            for line in lines:
                if line.amount_unreconciled:
                    perc = (
                        line.financial_amount_unreconciled /
                        line.amount_unreconciled)
                    # self.currency_id.round
                    financial_amount += line.amount * perc
            return financial_amount
        reconciled_financial_amount_ = (
            get_lines_financial_amount(self.line_cr_ids) -
            get_lines_financial_amount(self.line_dr_ids))
        if self.type == 'payment':
            reconciled_financial_amount_ = -1 * reconciled_financial_amount_
        # financial_amount = credit - debit + self.advance_amount
        # self.to_pay_amount = to_pay_amount
        self.reconciled_financial_amount_ = reconciled_financial_amount_


class AccountVoucherLine(models.Model):
    _inherit = "account.voucher.line"

    financial_amount_original = fields.Float(
        related='move_line_id.financial_debt',
        string='Financial Original Amount',
        # store=True,
    )
    financial_amount_unreconciled = fields.Float(
        related='move_line_id.financial_amount_residual',
        string='Financial Open Balance',
        # store=True,
    )
    # amount_residual
    # amount_residual_currency
    # @api.multi
    # def recompute_voucher_lines(
    #         self, partner_id, journal_id, price, currency_id, ttype, date):
    #     default = super(AccountVoucher, self).recompute_voucher_lines(
    #         partner_id, journal_id, price, currency_id, ttype, date)
    #     values = default.get('value', {})
    #     # if we pay from invioce, then we dont clean amount
    #     if self._context.get('invoice_id'):
    #         return default
    #     for val_cr in values.get('line_cr_ids', {}):
    #         if isinstance(val_cr, dict):
    #             val_cr.update({'amount': 0.0, 'reconcile': False})
    #     for val_dr in values.get('line_dr_ids', {}):
    #         if isinstance(val_dr, dict):
    #             val_dr.update({'amount': 0.0, 'reconcile': False})
    #     return default
