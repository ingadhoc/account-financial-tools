# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models, fields, api


class AccountDebtSummary(models.Model):
    _name = "account.debt.summary"
    _description = "Account Debt Summary"
    _auto = False
    _rec_name = 'date_maturity'
    # _order = 'id'
    _order = 'date desc, date_maturity desc'
    _depends = {
        'account.move.line': [
            'account_id', 'debit', 'credit', 'date_maturity', 'partner_id',
            'amount_currency',
        ],
    }

    partner_id = fields.Many2one(
        'res.partner',
        'Partner',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        'Currency',
        readonly=True,
    )
    amount_currency = fields.Float(
        readonly=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        'Company',
        readonly=True,
    )
    ref = fields.Char(
        readonly=True,
    )
    move_id = fields.Many2one(
        'account.move',
        'Move',
        readonly=True,
    )
    account_id = fields.Many2one(
        'account.account',
        'Account',
        readonly=True,
    )
    type = fields.Selection([
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
    ])
    maturity_dates = fields.Char(
        compute='get_date'
    )
    date = fields.Date(
        readonly=True,
    )
    date_maturity = fields.Date(
        readonly=True,
    )
    debit = fields.Float(
        readonly=True,
    )
    credit = fields.Float(
        readonly=True,
    )
    debt = fields.Float(
        readonly=True,
    )
    cumulative_debt = fields.Float(
        readonly=True,
        compute='_get_cumulative_debts'
    )
    financial_debt = fields.Float(
        readonly=True,
        compute='_get_cumulative_debts'
    )
    cumulative_financial_debt = fields.Float(
        readonly=True,
        compute='_get_cumulative_debts'
    )

    @api.multi
    def _get_cumulative_debts(self):
        """
        TODO ver si encontramos una forma de obtener el orden que esta pasando
        la vista y ordenar por ese criterio o directamente agregar un widget
        o algo que lo permita
        TODO tal vez convenga hacer el sorted en la consulta sql para no
        sobrecargar acá. Mas o menos debería ser algo como la que dejamos aca
        bajo comentada
        """
        cumulative_debt = 0.0
        cumulative_financial_debt = 0.0
        # we need to reorder records
        for line in reversed(self.search(
                [('id', 'in', self.ids)], order=self._order)):
            cumulative_debt += line.debt
            line.cumulative_debt = cumulative_debt
            financial_debt = line.currency_id and line.currency_id.compute(
                line.amount_currency,
                line.company_id.currency_id) or line.debt
            line.financial_debt = financial_debt
            cumulative_financial_debt += financial_debt
            line.cumulative_financial_debt = cumulative_financial_debt

# ACUMULATIVE FROM SQL
# SELECT *, SUM(balance) OVER(PARTITION BY partner_id ORDER BY rn) as acumulated
# FROM(
#     SELECT  ROW_NUMBER() OVER (ORDER BY m.date) AS rn, m.date, m.id, l.partner_id, l.date_maturity, SUM(l.debit) as debit,
#     SUM(l.credit) as credit, SUM(l.credit - l.debit) as balance
#         FROM account_move_line l
#         LEFT JOIN account_account a ON (l.account_id=a.id)
#         LEFT JOIN account_move m ON (l.move_id=m.id)
#         WHERE a.type IN ('payable', 'receivable')
#         GROUP BY  m.id, l.partner_id, l.date_maturity
# ) as asdasda

    @api.one
    @api.depends('move_id.line_id.date_maturity')
    def get_date(self):
        # TODO format lang
        self.maturity_dates = ','.join(self.move_id.line_id.filtered(
            lambda x: x.date_maturity).mapped('date_maturity'))

    def init(self, cr):
        tools.drop_view_if_exists(cr, self._table)
        # en realidad podemos usar este order by al final o no necesariamente
        # y podriamos usar move_id como id en vez de invitar uno, pero
        # aprovechamos a que los numeros queden ordenados
        # ORDER BY m.date ASC, l.date_maturity DESC
        query = """
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY m.date ASC, l.date_maturity DESC) AS id, m.ref,
            m.id as move_id, m.date, m.company_id, m.journal_id, a.type,
            l.partner_id, l.date_maturity, l.account_id, SUM(l.debit) as debit,
            SUM(l.amount_currency) as amount_currency, l.currency_id,
            SUM(l.credit) as credit, SUM(l.debit - l.credit) as debt
        FROM account_move_line l
        LEFT JOIN account_account a ON (l.account_id=a.id)
        LEFT JOIN account_move m ON (l.move_id=m.id)
        WHERE a.type IN ('payable', 'receivable')
        GROUP BY m.id, a.type, l.partner_id, l.currency_id, l.date_maturity,
            l.account_id
        """
        cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))
