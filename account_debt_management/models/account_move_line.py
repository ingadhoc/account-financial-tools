# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields
# from openerp.exceptions import Warning


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    debt = fields.Float(
        compute='_get_debt',
        )
    currency_debt = fields.Float(
        compute='_get_debt',
        )
    financial_debt = fields.Float(
        compute='_get_debt',
        )
    cumulative_debt = fields.Float(
        compute='_get_debt',
        )
    cumulative_financial_debt = fields.Float(
        compute='_get_debt',
        )

    @api.multi
    @api.depends('debit', 'credit')
    def _get_debt(self):
        payable_lines = self.search([
            ('id', 'in', self.ids),
            ('account_id.type', '=', 'payable'),
            ])
        receivable_lines = self.search([
            ('id', 'in', self.ids),
            ('account_id.type', '=', 'receivable'),
            ])
        for sign, lines in [(1.0, receivable_lines), (-1.0, payable_lines)]:
            cumulative_debt = 0.0
            cumulative_financial_debt = 0.0
            for line in lines:
                debt = line.debit - line.credit
                financial_debt = line.currency_id and line.currency_id.compute(
                    line.amount_currency,
                    line.account_id.company_id.currency_id) or debt
                # so we dont display 0.0 when no amount_currency
                cumulative_debt += debt
                cumulative_financial_debt += financial_debt

                if line.amount_currency:
                    line.currency_debt = sign * line.amount_currency
                line.debt = sign * debt
                line.financial_debt = sign * financial_debt
                line.cumulative_debt = sign * cumulative_debt
                line.cumulative_financial_debt = (
                    sign * cumulative_financial_debt)
