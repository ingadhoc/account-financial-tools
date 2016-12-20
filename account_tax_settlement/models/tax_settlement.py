# -*- coding: utf-8 -*-
from openerp import fields, api, models, _
from openerp.exceptions import ValidationError
import openerp.addons.decimal_precision as dp
import time


class account_tax_settlement_detail(models.Model):
    _name = 'account.tax.settlement.detail'
    _description = 'Account Tax Settlement Detail'

    tax_settlement_id = fields.Many2one(
        'account.tax.settlement',
        'Tax Settlement',
        required=True,
        ondelete='cascade',
        )
    tax_code_id = fields.Many2one(
        'account.tax.code',
        'Tax Code',
        required=True,
        )
    move_line_ids = fields.One2many(
        # TODO hacerlo m2m y verificar que a la hora de generar el asiento no se haya usado ya
        'account.move.line',
        'tax_settlement_detail_id',
        string="Move Lines",
        )
    tax_amount = fields.Float(
        _('Tax Amount'),
        compute='get_amounts',
        digits=dp.get_precision('Account'),
        )
    debit_amount = fields.Float(
        _('Debit Amount'),
        compute='get_amounts',
        digits=dp.get_precision('Account'),
        )
    credit_amount = fields.Float(
        _('Credit Amount'),
        compute='get_amounts',
        digits=dp.get_precision('Account'),
        )

    @api.one
    def get_move_lines(self):
        settlement = self.tax_settlement_id
        domain = [
            ('tax_code_id', '=', self.tax_code_id.id),
            # unsettle mlines
            ('tax_settlement_move_id', '=', False),
            ]
        self.move_line_ids = False

        if settlement.moves_state != 'all':
            domain.append(('move_id.state', '=', settlement.moves_state))

        if settlement.filter == 'filter_period':
            domain += [
                ('period_id', 'in', settlement.period_ids.ids)]
        elif settlement.filter == 'filter_date':
            domain += [
                ('move_id.date', '>=', settlement.date_from),
                ('move_id.date', '<', settlement.date_to)]
        else:
            domain.append(
                ('period_id.fiscalyear_id', '=', settlement.fiscalyear_id.id))
        move_lines = self.env['account.move.line'].search(domain)
        self.move_line_ids = move_lines

    @api.one
    @api.depends('move_line_ids.tax_amount', 'tax_code_id.sign')
    def get_amounts(self):
        self.tax_amount = self.tax_code_id.sign * sum(
            self.move_line_ids.mapped('tax_amount'))
        self.credit_amount = sum(
            self.move_line_ids.mapped('credit'))
        self.debit_amount = sum(
            self.move_line_ids.mapped('debit'))

    @api.multi
    def prepare_line_values(self):
        self.ensure_one()
        res = []
        grouped_lines = self.move_line_ids.read_group(
            domain=[('id', 'in', self.move_line_ids.ids)],
            fields=['id', 'debit', 'credit', 'tax_amount', 'account_id'],
            groupby=['account_id'],
            )

        for line in grouped_lines:
            # we create all moves, no matter amount = 0, to make posible
            # unreconciliation form this settlement
            # if not line['tax_amount'] and line['debit'] == line['credit']:
            #     continue

            debit = 0.0
            credit = 0.0
            if line['credit'] > line['debit']:
                debit = line['credit'] - line['debit']
            else:
                credit = line['debit'] - line['credit']

            vals = {
                'name': self.tax_settlement_id.name,
                'debit': debit,
                'credit': credit,
                'account_id': line['account_id'][0],
                'tax_code_id': self.tax_code_id.id,
                'tax_amount': -1.0 * line['tax_amount'],
            }
            res.append(vals)
        return res


class account_tax_settlement(models.Model):
    _name = 'account.tax.settlement'
    _description = 'Account Tax Settlement'
    _inherit = ['mail.thread']
    # _order = 'period_id desc'

    tax_codes_count = fields.Float(
        _('# Tax Codes'),
        compute='_get_tax_codes_count',
        )
    account_balance_amount = fields.Float(
        _('Account Balance Amount'),
        compute='_get_balance',
        digits=dp.get_precision('Account'),
        )
    tax_code_balance_amount = fields.Float(
        _('Tax Balance Amount'),
        compute='_get_balance',
        digits=dp.get_precision('Account'),
        )
    balance_account_id = fields.Many2one(
        'account.account',
        _('Balance Account'),
        compute='_get_balance',
        digits=dp.get_precision('Account'),
        )
    balance_tax_code_id = fields.Many2one(
        'account.tax.code',
        _('Balance Tax Code'),
        compute='_get_balance',
        digits=dp.get_precision('Account'),
        )
    move_line_ids = fields.One2many(
        related='move_id.line_id',
        readonly=True,
        )
    to_settle_move_line_ids = fields.Many2many(
        'account.move.line',
        compute='_get_to_settle_move_lines',
        # inverse='_set_to_settle_move_lines',
        string=_("Move Lines To Settle"),
        )

    # TODO analizar de implementar esta funcionalidad de poder borrar
    # lineas te move lines y que se borren del detail, no podriamos hacer
    # una nueva vista como queriamos, tendriamos que ponerlo en la misma
    # vista de tax settlement
    # @api.multi
    # def _set_to_settle_move_lines(self):
    #     actual_move_lines = self.to_settle_move_line_ids
    #     before_move_lines = self.mapped(
    #         'tax_settlement_detail_ids.move_line_ids')
    #     removed_move_lines = before_move_lines - actual_move_lines
    #     return True

    @api.one
    @api.depends('tax_settlement_detail_ids.move_line_ids')
    def _get_to_settle_move_lines(self):
        self.to_settle_move_line_ids = self.mapped(
            'tax_settlement_detail_ids.move_line_ids')

    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        ondelete='restrict',
        copy=False,
        help="Link to the automatically generated Journal Items."
        )
    filter = fields.Selection([
        ('filter_no', 'No Filters'),
        ('filter_date', 'Date'),
        ('filter_period', 'Periods')],
        "Filter by",
        default='filter_no',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    date = fields.Date(
        'Date',
        help='Date to be used on created move',
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    period_id = fields.Many2one(
        'account.period',
        help='Period to be used on created move',
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    period_ids = fields.Many2many(
        'account.period',
        'account_tax_settlement_period_rel',
        'settlement_id', 'period_id',
        'Periods',
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    date_from = fields.Date(
        "Start Date",
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    partner_id = fields.Many2one(
        related='journal_id.partner_id.commercial_partner_id'
        )
    date_to = fields.Date(
        "End Date",
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env[
            'res.company']._company_default_get('account.tax.settlement')
        )
    fiscalyear_id = fields.Many2one(
        'account.fiscalyear', 'Fiscal Year', required=True,
        readonly=True, states={'draft': [('readonly', False)]},
        )
    # type = fields.Selection(
    #     [('sale', 'Sale'), ('purchase', 'Purchase')],
    #     "Type", required=True)
    journal_id = fields.Many2one(
        'account.journal',
        'Journal',
        domain=[('type', '=', 'tax_settlement'), ('tax_code_id', '!=', False)],
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('presented', 'Presented'),
        ('done', 'Done'),
        ('cancel', 'Cancel')],
        'State',
        required=True,
        default='draft'
        )
    note = fields.Html(
        'Notes'
        )
    name = fields.Char(
        _('Title'),
        compute='_get_name')
    moves_state = fields.Selection(
        [('posted', 'Posted Entries'), ('all', 'All Entries')],
        'Moves Status',
        required=True,
        readonly=True,
        default='posted',
        states={'draft': [('readonly', False)]},
        )
    tax_settlement_detail_ids = fields.One2many(
        'account.tax.settlement.detail',
        'tax_settlement_id',
        'Detail',
        readonly=True,
        states={'draft': [('readonly', False)]},
        )
    payment_ids = fields.Many2many(
        'account.move.line',
        string=_('Payments'),
        compute='_compute_payments')
    residual = fields.Float(
        string=_('Balance'),
        digits=dp.get_precision('Account'),
        compute='_compute_residual', store=True,
        help=_("Remaining amount due."))

    @api.multi
    def settlement_pay(self):
        self.ensure_one()
        return self.move_id.with_context(
            from_settlement=True).create_voucher('payment')

    @api.one
    @api.depends(
        'move_id.line_id.reconcile_id.line_id',
        'move_id.line_id.reconcile_partial_id.line_partial_ids',
    )
    def _compute_payments(self):
        partial_lines = lines = self.env['account.move.line']
        for line in self.move_id.line_id:
            if line.account_id != self.balance_account_id:
                continue
            if line.reconcile_id:
                lines |= line.reconcile_id.line_id
            elif line.reconcile_partial_id:
                lines |= line.reconcile_partial_id.line_partial_ids
            partial_lines += line
        self.payment_ids = (lines - partial_lines).sorted()

    @api.one
    @api.depends(
        'state',
        'move_id.line_id.account_id.type',
        'move_id.line_id.amount_residual',
        # Fixes the fact that move_id.line_id.amount_residual, being not stored and old API, doesn't trigger recomputation
        'move_id.line_id.reconcile_id',
        'move_id.line_id.amount_residual_currency',
        'move_id.line_id.currency_id',
        'move_id.line_id.reconcile_partial_id.line_partial_ids.invoice.type',
    )
    def _compute_residual(self):
        self.residual = 0.0
        self.residual = self.move_id.payable_residual

    @api.constrains('state', 'residual')
    def _check_done(self):
        if self.state == 'presented' and self.residual == 0.0:
            self.state = 'done'
        elif self.state == 'done' and self.residual != 0.0:
            self.state = 'presented'

    @api.one
    @api.depends('tax_settlement_detail_ids')
    def _get_tax_codes_count(self):
        self.tax_codes_count = len(self.tax_settlement_detail_ids)

    @api.one
    @api.depends('tax_settlement_detail_ids')
    def _get_balance(self):
        credit_amount = sum(
            self.tax_settlement_detail_ids.mapped('credit_amount'))
        debit_amount = sum(
            self.tax_settlement_detail_ids.mapped('debit_amount'))
        tax_code_balance_amount = sum(
            self.tax_settlement_detail_ids.mapped('tax_amount'))
        account_balance_amount = credit_amount - debit_amount
        if account_balance_amount <= 0:
            balance_account = self.journal_id.default_credit_account_id
            balance_tax_code = self.journal_id.default_credit_tax_code_id
        else:
            balance_account = self.journal_id.default_debit_account_id
            balance_tax_code = self.journal_id.default_debit_tax_code_id
        self.account_balance_amount = account_balance_amount
        self.balance_account_id = balance_account.id
        self.balance_tax_code_id = balance_tax_code.id
        self.tax_code_balance_amount = tax_code_balance_amount

    @api.multi
    def action_present(self):
        self.create_move()

    @api.one
    def action_cancel(self):
        move = self.move_id
        self.move_id = False
        move.unlink()
        self.state = 'cancel'

    @api.multi
    def action_to_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def get_final_line_vals(self):
        res = {}
        if not self.partner_id:
            raise ValidationError(_(
                'No Partner configured on journal'))
        if not self.balance_account_id:
            raise ValidationError(_(
                'No Balance account configured on journal'))
        for line in self:
            account_balance_amount = self.account_balance_amount
            if account_balance_amount < 0:
                credit = 0.0
                debit = -1. * account_balance_amount
                tax_code_balance_amount = -1. * self.tax_code_balance_amount
            else:
                credit = account_balance_amount
                debit = 0.0
                tax_code_balance_amount = self.tax_code_balance_amount
            vals = {
                'partner_id': self.partner_id.id,
                'name': self.name,
                'debit': debit,
                'credit': credit,
                'account_id': self.balance_account_id.id,
                'tax_code_id': self.balance_tax_code_id.id,
                'tax_amount': tax_code_balance_amount,
            }
            res[self.id] = vals
        return res

    @api.one
    def create_move(self):
        if not self.date:
            self.date = fields.Date.context_today(self)

        period = self.period_id
        if not self.period_id:
            period = period.with_context(company_id=self.company_id.id).find(
                self.date)[:1]

        # TODO improove here, direct comparison didnt work
        if abs(self.tax_code_balance_amount - self.account_balance_amount) >= 0.001:
            raise ValidationError(_('Account Balance and Tax Balance must be equal.'))
        if not self.journal_id.sequence_id:
            raise ValidationError(_('Please define a sequence on the journal.'))

        to_settle_move_lines = self.mapped(
            'tax_settlement_detail_ids.move_line_ids')

        # write move id on settled tax move lines
        if to_settle_move_lines.filtered('tax_settlement_move_id'):
            raise ValidationError(_(
                'You can not settle lines that has already been settled!\n'
                '* Lines ids: %s') % (
                to_settle_move_lines.filtered('tax_settlement_move_id').ids))

        name = self.journal_id.sequence_id._next()
        move_line_env = self.env['account.move.line']
        move_vals = {
            'ref': name,
            'name': self.name,
            'period_id': period.id,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            }
        move = self.move_id.create(move_vals)
        created_move_line_ids = []
        debit = 0.0
        credit = 0.0
        for tax in self:
            for tax in self.tax_settlement_detail_ids:
                for line_vals in tax.prepare_line_values():
                    credit += line_vals['credit']
                    debit += line_vals['debit']
                    line_vals['move_id'] = move.id
                    line_vals['tax_settlement_move_id'] = move.id
                    # line_vals['ref'] = name
                    created_move_line_ids.append(
                        move_line_env.create(line_vals).id)

        final_line_vals = self.get_final_line_vals()[self.id]
        final_line_vals['move_id'] = move.id
        move_line_env.create(final_line_vals)

        to_settle_move_lines.write({'tax_settlement_move_id': move.id})

        self.write({
            'move_id': move.id,
            'state': 'presented',
            'period_id': period.id,
            })

    @api.one
    @api.constrains('company_id', 'journal_id')
    def check_company(self):
        if self.company_id != self.journal_id.company_id:
            raise ValidationError(_('Tax settlement company and journal company must be the same'))

    @api.one
    def _get_name(self):
        if self.filter == 'filter_period' and self.period_ids:
            filter_name = ', '.join(self.period_ids.mapped('name'))
        elif self.filter == 'filter_date' and self.date_from and self.date_to:
            filter_name = "%s - %s" % (self.date_from, self.date_to)
        else:
            filter_name = self.fiscalyear_id.name
        name = _('Tax Settlment %s') % (filter_name)
        self.name = name

    @api.one
    def compute(self):
        actual_tax_code_ids = [
            x.tax_code_id.id for x in self.tax_settlement_detail_ids]
        for tax_code in self.env['account.tax.code'].search([
                ('id', 'child_of', self.journal_id.tax_code_id.id),
                ('id', 'not in', actual_tax_code_ids),
                ('type', '!=', 'view'),
                ]):
            self.tax_settlement_detail_ids.create({
                'tax_code_id': tax_code.id,
                'tax_settlement_id': self.id,
                })
        self.tax_settlement_detail_ids.get_move_lines()

    @api.onchange('company_id')
    def change_company(self):
        now = time.strftime('%Y-%m-%d')
        company_id = self.company_id.id
        domain = [('company_id', '=', company_id),
                  ('date_start', '<', now), ('date_stop', '>', now)]
        fiscalyears = self.env['account.fiscalyear'].search(domain, limit=1)
        self.fiscalyear_id = fiscalyears

    # @api.onchange('fiscalyear_id')
    # def change_fiscalyear(self):
    #     # TODO arreglar este onchange
    #     tax_settlement = self.search(
    #         [('company_id', '=', self.company_id.id),
    #          ('fiscalyear_id', '=', self.fiscalyear_id.id)],
    #         order='period_id desc', limit=1)
    #     if tax_settlement:
    #         next_period = self.env['account.period'].search(
    #             [('company_id', '=', self.company_id.id),
    #              ('fiscalyear_id', '=', self.fiscalyear_id.id),
    #              ('date_start', '>', tax_settlement.period_id.date_start),
    #              ], limit=1)
    #     else:
    #         next_period = self.env['account.period'].search(
    #             [('company_id', '=', self.company_id.id),
    #              ('fiscalyear_id', '=', self.fiscalyear_id.id)], limit=1)
    #     self.period_id = next_period
