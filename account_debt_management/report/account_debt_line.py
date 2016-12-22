# -*- coding: utf-8 -*-
from openerp import tools
from openerp import models, fields, api


class AccountDebtLine(models.Model):
    _name = "account.debt.line"
    _description = "Account Debt Line"
    _auto = False
    # we need id on order so we can get right amount when accumulating
    # move_id desc porque move id ordena ultimo arriba
    _order = 'date asc, date_maturity asc, move_id desc, id'
    # _order = 'date desc, date_maturity desc, move_id, id'
    _depends = {
        'res.partner': [
            'user_id',
        ],
        'account.move.line': [
            'account_id', 'debit', 'credit', 'date_maturity', 'partner_id',
            'amount_currency',
        ],
    }

    date = fields.Date(
        readonly=True
    )
    date_maturity = fields.Date(
        readonly=True
    )
    ref = fields.Char(
        'Reference',
        readonly=True
    )
    amount = fields.Monetary(
        readonly=True,
        currency_field='company_currency_id',
    )
    amount_residual = fields.Monetary(
        readonly=True,
        string='Residual Amount',
        currency_field='company_currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        'Currency',
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        'Commercial',
        readonly=True
    )
    amount_currency = fields.Monetary(
        readonly=True,
        currency_field='currency_id',
    )
    amount_residual_currency = fields.Monetary(
        readonly=True,
        string='Residual Amount in Currency',
        currency_field='currency_id',
    )
    move_id = fields.Many2one(
        'account.move',
        'Entry',
        readonly=True
    )
    move_line_id = fields.Many2one(
        'account.move.line',
        'Entry line',
        readonly=True
    )
    # period_id = fields.Many2one(
    #     'account.period',
    #     'Period',
    #     readonly=True
    # )
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
    move_state = fields.Selection(
        [('draft', 'Unposted'), ('posted', 'Posted')],
        'Status',
        readonly=True
    )
    reconciled = fields.Boolean(
    )
    full_reconcile_id = fields.Many2one(
        'account.full.reconcile',
        'Matching Number',
        readonly=True
    )
    # reconcile_partial_id = fields.Many2one(
    #     'account.move.reconcile',
    #     'Partial Reconciliation',
    #     readonly=True
    # )
    partner_id = fields.Many2one(
        'res.partner',
        'Partner',
        readonly=True
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Analytic Account',
        readonly=True
    )
    account_type = fields.Many2one(
        'account.account.type',
        'Account Type',
        readonly=True
    )
    type = fields.Selection([
        ('receivable', 'Receivable'),
        ('payable', 'Payable')],
        'Type',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        readonly=True
    )

    # computed fields
    display_name = fields.Char(
        compute='get_display_name'
    )
    financial_amount = fields.Monetary(
        related='move_line_id.financial_amount',
        # compute='_get_amounts',
        currency_field='company_currency_id',
    )
    # balance = fields.Monetary(
    #     compute='_get_amounts',
    #     currency_field='company_currency_id',
    # )
    financial_amount_residual = fields.Monetary(
        related='move_line_id.financial_amount_residual',
        currency_field='company_currency_id',
    )
    # financial_amount_residual = fields.Monetary(
    #     compute='_get_amounts',
    #     currency_field='company_currency_id',
    # )
    # financial_balance = fields.Monetary(
    #     compute='_get_amounts',
    #     currency_field='company_currency_id',
    # )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )

    @api.one
    def get_display_name(self):
        # usamos display_name para que contenga doc number o name
        # luego si el ref es igual al name del move no lo mostramos
        display_name = self.move_id.display_name
        ref = False
        # because account voucher replace / with ''
        move_names = [self.move_id.name, self.move_id.name.replace('/', '')]
        # solo agregamos el ref del asiento o el name del line si son distintos
        # a el name del asiento
        if self.ref and self.ref not in move_names:
            ref = self.ref
        elif (
                self.move_line_id.name and
                self.move_line_id.name != '/' and
                self.move_line_id.name not in move_names):
            ref = self.move_line_id.name
        if ref:
            display_name = '%s (%s)' % (display_name, ref)
        self.display_name = display_name

    # @api.multi
    # @api.depends('amount_residual_currency')
    # # @api.depends('amount', 'amount_currency')
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
    #         financial_amount_residual = (
    #             line.currency_id and line.currency_id.compute(
    #                 line.amount_residual_currency,
    #                 line.company_id.currency_id) or line.amount_residual)
    #         line.financial_amount = financial_amount
    #         financial_balance += financial_amount
    #         line.financial_balance = financial_balance
    #         line.financial_amount_residual = financial_amount_residual

    def init(self, cr):
        tools.drop_view_if_exists(cr, self._table)
        query = """
            SELECT
                l.id as id,
                l.id as move_line_id,
                am.date as date,
                l.date_maturity as date_maturity,
                am.ref as ref,
                am.state as move_state,
                l.full_reconcile_id as full_reconcile_id,
                l.reconciled as reconciled,
                -- l.reconcile_partial_id as reconcile_partial_id,
                l.move_id as move_id,
                l.partner_id as partner_id,
                am.company_id as company_id,
                am.journal_id as journal_id,
                -- p.fiscalyear_id as fiscalyear_id,
                -- am.period_id as period_id,
                l.account_id as account_id,
                l.analytic_account_id as analytic_account_id,
                a.internal_type as type,
                a.user_type_id as account_type,
                l.currency_id as currency_id,
                l.amount_currency as amount_currency,
                l.amount_residual_currency as amount_residual_currency,
                l.amount_residual as amount_residual,
                pa.user_id as user_id,
                l.balance as amount
                -- coalesce(l.debit, 0.0) - coalesce(l.credit, 0.0) as amount
            FROM
                account_move_line l
                left join account_account a on (l.account_id = a.id)
                left join account_move am on (am.id=l.move_id)
                -- left join account_period p on (am.period_id=p.id)
                left join res_partner pa on (l.partner_id=pa.id)
            WHERE
                -- l.state != 'draft' and
                a.internal_type IN ('payable', 'receivable')
        """
        cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        view_id = False
        # TODO ver si queremos devolver lista si hay mas de uno
        record = self.env['account.invoice'].search(
            [('move_id', '=', self.move_id.id)], limit=1)
        if not record:
            record = self.env['account.payment'].search(
                [('move_line_ids', '=', self.id)], limit=1)
            if record:
                view_id = self.env['ir.model.data'].xmlid_to_res_id(
                    'account.view_account_payment_form')
            else:
                record = self.move_id
        else:
            # if invoice, we choose right view
            if record.type in ['in_refund', 'in_invoice']:
                view_id = self.env.ref('account.invoice_supplier_form').id
            else:
                view_id = self.env.ref('account.invoice_form').id

        return {
            'type': 'ir.actions.act_window',
            'res_model': record._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': record.id,
            'view_id': view_id,
        }
