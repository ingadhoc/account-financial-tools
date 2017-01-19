# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp


class AccountBookLine(models.Model):
    _name = "account.book.line"
    _description = "Account Book Line"
    _auto = False
    # we need id on order so we can get right amount when accumulating
    # move_id desc porque move id ordena ultimo arriba
    _order = 'number_in_book, credit, date, id'
    # _order = 'date desc, date_maturity desc, move_id, id'
    # _depends = {
    #     'res.partner': [
    #         'user_id',
    #     ],
    #     'account.move.line': [
    #         'account_id', 'debit', 'credit', 'date_maturity', 'partner_id',
    #         'amount_currency',
    #     ],
    # }

    number_in_book = fields.Char(
        readonly=True
    )
    date = fields.Date(
        readonly=True
    )
    # ref = fields.Char(
    #     'Reference',
    #     readonly=True
    # )
    debit = fields.Float(
        readonly=True,
        digits=dp.get_precision('Account'),
    )
    credit = fields.Float(
        readonly=True,
        digits=dp.get_precision('Account'),
    )
    # move_id = fields.Many2one(
    #     'account.move',
    #     'Entry',
    #     readonly=True
    # )
    # move_line_id = fields.Many2one(
    #     'account.move.line',
    #     'Entry line',
    #     readonly=True
    # )
    period_id = fields.Many2one(
        'account.period',
        'Period',
        readonly=True
    )
    account_id = fields.Many2one(
        'account.account',
        'Account',
        readonly=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        'Journal',
        readonly=True
    )
    # fiscalyear_id = fields.Many2one(
    #     'account.fiscalyear',
    #     'Fiscal Year',
    #     readonly=True
    # )
    state = fields.Selection(
        [('draft', 'Unposted'), ('posted', 'Posted')],
        'Status',
        readonly=True
    )
    # partner_id = fields.Many2one(
    #     'res.partner',
    #     'Partner',
    #     readonly=True
    # )
    # company_id = fields.Many2one(
    #     'res.company',
    #     'Company',
    #     readonly=True
    # )

    # computed fields
    # display_name = fields.Char(
    #     compute='get_display_name'
    # )
    # financial_amount = fields.Float(
    #     compute='_get_amounts',
    # )
    # balance = fields.Float(
    #     compute='_get_amounts',
    # )
    # financial_balance = fields.Float(
    #     compute='_get_amounts',
    # )
    # company_currency_id = fields.Many2one(
    #     related='company_id.currency_id',
    #     readonly=True,
    # )

    # @api.one
    # def get_display_name(self):
    #     # usamos display_name para que contenga doc number o name
    #     # luego si el ref es igual al name del move no lo mostramos
    #     display_name = self.move_id.display_name
    #     ref = False
    #     # because account voucher replace / with ''
    #     move_names = [self.move_id.name, self.move_id.name.replace('/', '')]
    #     # solo agregamos el ref del asiento o el name del line si son distintos
    #     # a el name del asiento
    #     if self.ref and self.ref not in move_names:
    #         ref = self.ref
    #     elif (
    #             self.move_line_id.name and
    #             self.move_line_id.name != '/' and
    #             self.move_line_id.name not in move_names):
    #         ref = self.move_line_id.name
    #     if ref:
    #         display_name = '%s (%s)' % (display_name, ref)
    #     self.display_name = display_name

    # @api.multi
    # @api.depends('amount', 'amount_currency')
    # def _get_amounts(self):
    #     """
    #     If debt_together in context then we discount payables and make
    #     cumulative all together
    #     """
    #     balance = 0.0
    #     financial_balance = 0.0
    #     # we need to reorder records
    #     # for line in reversed(self.search(
    #     #         [('id', 'in', self.ids)], order=self._order)):
    #     for line in self.search([('id', 'in', self.ids)], order=self._order):
    #         balance += line.amount
    #         line.balance = balance
    #         financial_amount = line.currency_id and line.currency_id.compute(
    #             line.amount_currency,
    #             line.company_id.currency_id) or line.amount
    #         line.financial_amount = financial_amount
    #         financial_balance += financial_amount
    #         line.financial_balance = financial_balance

    def init(self, cr):
        tools.drop_view_if_exists(cr, self._table)
        query = """
            SELECT
                row_number() OVER () AS id,
                am.number_in_book,
                am.period_id,
                am.journal_id,
                am.state,
                max(am.date) as date,
                -- 'Varios' as partner,
                -- 'Varios' as reference,
                aml.account_id,
                sum(debit) as debit,
                sum(credit) as credit
            FROM account_move am join account_move_line aml
                on aml.move_id = am.id
            -- WHERE number_in_book is not null
            GROUP BY
                am.period_id, am.number_in_book, am.journal_id,
                aml.account_id, am.state
            -- ORDER BY number_in_book
        """
        cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))
