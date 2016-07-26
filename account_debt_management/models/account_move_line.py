# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields
# from openerp.exceptions import Warning


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # debt = fields.Float(
    #     compute='_get_debt',
    #     string='Amount',
    # )
    # currency_debt = fields.Float(
    #     compute='_get_debt',
    #     string='Currency Amount',
    # )
    financial_amount_residual = fields.Float(
        compute='_get_debt',
        string='Residual Financial Amount',
    )
    financial_debt = fields.Float(
        compute='_get_debt',
        string='Financial Amount',
    )
    # cumulative_debt = fields.Float(
    #     compute='_get_debt',
    #     string='Balance',
    # )
    # cumulative_financial_debt = fields.Float(
    #     compute='_get_debt',
    #     string='Financial Balance',
    # )

    @api.multi
    @api.depends('debit', 'credit')
    def _get_debt(self):
        """
        If debt_together in context then we discount payables and make
        cumulative all together
        """
        if self._context.get('debt_together', False):
            # we research to get right order
            search_list = [(1.0, self.search([('id', 'in', self.ids)]))]
        else:
            payable_lines = self.search([
                ('id', 'in', self.ids),
                ('account_id.type', '=', 'payable'),
            ])
            receivable_lines = self.search([
                ('id', 'in', self.ids),
                ('account_id.type', '=', 'receivable'),
            ])
            search_list = [(1.0, receivable_lines), (-1.0, payable_lines)]
        for sign, lines in search_list:
            cumulative_debt = 0.0
            cumulative_financial_debt = 0.0
            for line in reversed(lines):
                debt = line.debit - line.credit
                financial_debt = line.currency_id and line.currency_id.compute(
                    line.amount_currency,
                    line.account_id.company_id.currency_id) or debt
                financial_amount_residual = line.currency_id and line.currency_id.compute(
                    line.amount_residual_currency,
                    line.account_id.company_id.currency_id) or line.amount_residual_currency
                # so we dont display 0.0 when no amount_currency
                cumulative_debt += debt
                cumulative_financial_debt += financial_debt

                if line.amount_currency:
                    line.currency_debt = sign * line.amount_currency
                line.debt = sign * debt
                line.financial_debt = sign * financial_debt
                # no need for sign, already signed
                line.financial_amount_residual = financial_amount_residual
                line.cumulative_debt = sign * cumulative_debt
                line.cumulative_financial_debt = (
                    sign * cumulative_financial_debt)
