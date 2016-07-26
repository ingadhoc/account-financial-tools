# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    financial_amount_residual = fields.Float(
        compute='_get_financial_amounts',
        string='Residual Financial Amount',
    )
    financial_amount = fields.Float(
        compute='_get_financial_amounts',
        string='Financial Amount',
    )

    @api.multi
    @api.depends('debit', 'credit')
    def _get_financial_amounts(self):
        for line in self:
            financial_amount = (
                line.currency_id and line.currency_id.compute(
                    line.amount_currency,
                    line.account_id.company_id.currency_id) or (
                    line.debit - line.credit))
            financial_amount_residual = (
                line.currency_id and line.currency_id.compute(
                    line.amount_residual_currency,
                    line.account_id.company_id.currency_id) or
                line.amount_residual_currency)
            line.financial_amount = financial_amount
            line.financial_amount_residual = financial_amount_residual
