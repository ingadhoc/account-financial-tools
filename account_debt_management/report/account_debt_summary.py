# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models, fields, api


class AccountDebtSummary(models.Model):
    _name = "account.debt.summary"
    _description = "Account Debt Summary"
    _auto = False
    _order = 'date desc, next_maturity_date desc'
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
    date = fields.Date(
        readonly=True,
    )
    last_maturity_date = fields.Date(
        readonly=True,
        string='Last Maturity'
    )
    next_maturity_date = fields.Date(
        readonly=True,
        string='Next Maturity'
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
    reconciled = fields.Boolean(
        readonly=True,
        help='Reconciled?'
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
    # computed fields
    maturity_dates = fields.Char(
        compute='get_date'
    )
    move_line_ids = fields.One2many(
        'account.move.line',
        compute='get_move_lines',
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    display_name = fields.Char(
        compute='get_display_name'
    )

    @api.one
    def get_display_name(self):
        self.display_name = '%s%s' % (
            self.move_id.display_name,
            self.move_id.display_name != self.ref and ' (%s)' % self.ref or '')

    @api.one
    def get_move_lines(self):
        if self.reconciled:
            domain = [('reconcile_id', '!=', False)]
        else:
            domain = [('reconcile_id', '=', False)]

        move_lines = self.move_line_ids.search(domain + [
            ('partner_id', '=', self.partner_id.id),
            ('move_id', '=', self.move_id.id),
            ('account_id.type', '=', self.type),
        ])
        self.move_line_ids = move_lines.ids

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
            lambda x: x.date_maturity and not x.reconcile_id).mapped(
            'date_maturity'))

    def init(self, cr):
        tools.drop_view_if_exists(cr, self._table)
        # en realidad podemos usar este order by al final o no necesariamente
        # y podriamos usar move_id como id en vez de invitar uno, pero
        # aprovechamos a que los numeros queden ordenados
        # ORDER BY m.date ASC, l.date_maturity DESC
        # TODO tal vez sea interesante agrupar por fecha de vencimiento para
        # que aparezca una linea por cada vencimiento
        query = """
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY m.date ASC) AS id, m.ref,
            m.id as move_id, m.date, m.company_id, m.journal_id, a.type,
            l.partner_id, Max(l.date_maturity) as last_maturity_date, Min(l.date_maturity) as next_maturity_date,
            (l.reconcile_id is not null) as reconciled, l.account_id, SUM(l.debit) as debit,
            -- Min(l.reconcile_id) as reconciled, l.account_id, SUM(l.debit) as debit,
            SUM(l.amount_currency) as amount_currency, l.currency_id,
            SUM(l.credit) as credit, SUM(l.debit - l.credit) as debt
        FROM account_move_line l
        LEFT JOIN account_account a ON (l.account_id=a.id)
        LEFT JOIN account_move m ON (l.move_id=m.id)
        WHERE a.type IN ('payable', 'receivable')
        -- GROUP BY m.id, a.type, l.partner_id, l.currency_id, l.account_id
        GROUP BY m.id, a.type, l.partner_id, l.currency_id, l.account_id, l.reconcile_id
        """
        # query = """
        # SELECT
        #     ROW_NUMBER() OVER (
        #         ORDER BY m.date ASC, l.date_maturity DESC) AS id, m.ref,
        #     m.id as move_id, m.date, m.company_id, m.journal_id, a.type,
        #     l.partner_id, l.date_maturity, l.account_id, SUM(l.debit) as debit,
        #     SUM(l.amount_currency) as amount_currency, l.currency_id,
        #     SUM(l.credit) as credit, SUM(l.debit - l.credit) as debt
        # FROM account_move_line l
        # LEFT JOIN account_account a ON (l.account_id=a.id)
        # LEFT JOIN account_move m ON (l.move_id=m.id)
        # WHERE a.type IN ('payable', 'receivable')
        # GROUP BY m.id, a.type, l.partner_id, l.currency_id, l.date_maturity,
        #     l.account_id
        # """
        cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        domain = [
            # TODO ver si agregamos esta condicion para asientos de varios
            # partners
            # ('partner_id.commercial_partner_id', '=', self.partner_id.id),
            ('move_id', '=', self.move_id.id),
        ]
        view_id = False
        # TODO ver si queremos devolver lista si hay mas de uno
        record = self.env['account.invoice'].search(domain, limit=1)
        if not record:
            record = self.env['account.voucher'].search(domain, limit=1)
            if record:
                if record.type == 'receipt':
                    view_id = self.env['ir.model.data'].xmlid_to_res_id(
                        'account_voucher.view_vendor_receipt_form')
                elif record.type == 'payment':
                    view_id = self.env['ir.model.data'].xmlid_to_res_id(
                        'account_voucher.view_vendor_payment_form')
            else:
                record = self.move_id

        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': record.id,
            'view_id': view_id,
        }
