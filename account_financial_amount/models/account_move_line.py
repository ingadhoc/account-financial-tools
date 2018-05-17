##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    financial_amount_residual = fields.Monetary(
        compute='_compute_financial_amounts',
        string='Residual Financial Amount',
        currency_field='company_currency_id',
    )
    financial_amount = fields.Monetary(
        compute='_compute_financial_amounts',
        string='Financial Amount',
        currency_field='company_currency_id',
    )

    @api.multi
    @api.depends('debit', 'credit')
    def _compute_financial_amounts(self):
        for line in self:
            financial_amount = (
                line.currency_id and line.currency_id.compute(
                    line.amount_currency,
                    line.account_id.company_id.currency_id) or (
                    line.balance))
            financial_amount_residual = (
                line.currency_id and line.currency_id.compute(
                    line.amount_residual_currency,
                    line.account_id.company_id.currency_id) or
                line.amount_residual)
            line.financial_amount = financial_amount
            line.financial_amount_residual = financial_amount_residual
