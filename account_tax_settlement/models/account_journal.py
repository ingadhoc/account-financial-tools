# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import ValidationError
from openerp.tools.misc import formatLang
from dateutil.relativedelta import relativedelta
import datetime


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # settlement_tax = fields.Selection(
    settlement_tax = fields.Selection(
        [],
        string='Impuesto de liquidación',
        help='Elija un impuesto si desea utilizar este diario para las '
        'liquidaciones de dicho impuesto.'
    )
    settlement_partner_id = fields.Many2one(
        'res.partner',
        'Partner de liquidación',
        oldname='partner_id',
    )
    settlement_financial_report_id = fields.Many2one(
        'account.financial.html.report',
        'Informe de liquidación',
    )
    # lo hacemos con etiquetas ya que se puede resolver con datos en plan
    # de cuentas sin incorporar lógica
    settlement_account_tag_ids = fields.Many2many(
        'account.account.tag',
        'account_journal_account_tag',
        auto_join=True,
        string='Etiquetas de cuentas liquidadas',
        # string='Settlement account tags',
        help="Accounts with this tags are going to be settled"
    )

    @api.multi
    @api.constrains('settlement_tax', 'type')
    def check_settlement_tax(self):
        for rec in self:
            if rec.settlement_tax:
                if rec.type != 'general':
                    raise ValidationError(_(
                        'Solo se puede usar "Impuesto de liquidación" en '
                        'diarios del tipo "Miscelánea"'))
                if not rec.settlement_partner_id:
                    raise ValidationError(_(
                        'Si usa "Impuesto de liquidación" debe setear un '
                        '"Partner de liquidación"'))
                if not rec.default_debit_account_id or \
                        not rec.default_credit_account_id:
                    raise ValidationError(_(
                        'Si usa "Impuesto de liquidación" debe setear cuentas '
                        'de débito y crédito'))

    @api.multi
    def _get_tax_settlement_grouped_move_lines(self, move_lines=None):
        grouped_move_lines = []
        for account in move_lines.mapped('account_id'):
            grouped_move_lines.append({
                'account': account,
                'move_lines': move_lines.filtered(
                    lambda x: x.account_id == account),
            })
        return grouped_move_lines

    @api.multi
    def _get_tax_settlement_entry_vals(self, grouped_move_lines):
        self.ensure_one()
        # get date, period and name
        # name = journal.sequence_id._next()
        # TODO tal vez sea interesante usar un nombre mas interesante?
        ref = self.name
        new_move_lines = []
        debit = 0.0
        credit = 0.0
        amount_currency = 0.0
        # hacemos esto para verificar que todos sean de la misma moneda
        currency = self.env['res.currency']
        for group in grouped_move_lines:
            group_debit = sum(group['move_lines'].mapped('debit'))
            group_credit = sum(group['move_lines'].mapped('credit'))
            group_amount_currency = -sum(group['move_lines'].mapped(
                'amount_currency'))
            currency |= group['move_lines'].mapped('currency_id')
            if len(currency) > 1:
                raise ValidationError(_(
                    'Los apuntes a liquidar deben ser todas de la misma '
                    'moneda.\n'
                    '* Apuntes contables: %s\n'
                    '* Monedas: %s') % (group['move_lines'], currency.ids))
            debit += group_debit
            credit += group_credit
            amount_currency += group_amount_currency
            vals = {
                'name': ref,
                'debit': group_credit,
                'credit': group_debit,
                'account_id': group['account'].id,
                # en realidad no hace falta descontar el impuesto, o si?
                # 'tax_id': group['tax_id'].id,
                'amount_currency': group_amount_currency,
                'currency_id': currency.id,
            }
            new_move_lines.append((0, False, vals))

        # volvemos a verificar ya que distintos grupos podrian haber tenido
        # distintas monedas
        if len(currency) > 1:
            raise ValidationError(_(
                'Los apuntes a liquidar deben ser todas de la misma moneda.\n'
                '* Monedas: %s') % (currency.ids))

        # check account payable
        if debit < credit:
            account = self.default_debit_account_id
            debit = 0.0
            credit = credit - debit
        else:
            account = self.default_credit_account_id
            credit = 0.0
            debit = debit - credit

        new_move_lines.append((0, False, {
            'partner_id': self.settlement_partner_id.id,
            'name': self.name,
            'debit': debit,
            'credit': credit,
            'account_id': account.id,
            'amount_currency': amount_currency,
            'currency_id': currency.id,
            # TODO que tax id usamos?
            # 'tax_id': ,
        }))

        date = fields.Date.today()
        name = self.sequence_id.next_by_id()
        move_vals = {
            'ref': ref,
            'name': name,
            'date': date,
            'journal_id': self.id,
            'company_id': self.company_id.id,
            'line_ids': new_move_lines,
        }
        return move_vals

    @api.multi
    def create_tax_settlement_entry(self, move_lines):
        self.ensure_one()
        if not self.settlement_tax:
            raise ValidationError(_(
                'Settlement only allowed on journals with Settlement Tax'))
        # if not self.journal_id.sequence_id:
        #     raise ValidationError(
        #         _('Please define a sequence on the journal.'))
        # queremos esta restriccion?
        # if to_settle_move_lines.filtered('tax_settlement_move_id'):
        #     raise ValidationError(_(
        #         'You can not settle lines that has already been settled!\n'
        #         '* Lines ids: %s') % (
        #         to_settle_move_lines.filtered('tax_settlement_move_id').ids))
        # if not self.tax_id:
        #     raise ValidationError(_(
        #         'Settlement only allowed for journal items with tax code'))

        # en realidad no, porque saldos a favor no requiere que sea a pagar..
        # check account type so that we can create a debt
        # if account.type != 'payable':
        #     raise ValidationError(_(
        #         'La cuenta de contrapartida en diarios de liquidación debe '
        #         'ser a pagar. Account id %s' % account.id))

        grouped_move_lines = self._get_tax_settlement_grouped_move_lines(
            move_lines)
        vals = self._get_tax_settlement_entry_vals(grouped_move_lines)
        move = self.env['account.move'].create(vals)
        move_lines.write({'tax_settlement_move_id': move.id})
        move.post()
        return move

    @api.multi
    def get_journal_dashboard_datas(self):
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        company = self.company_id
        currency = self.currency_id or self.company_id.currency_id
        report = self.settlement_financial_report_id
        report_position = 0.0

        if report:
            currency_table = {}
            # para el caso donde el usuario esta en una cia con moneda
            # distinta a la moneda de la cia del diario
            used_currency = self.env.user.company_id.currency_id
            # no importa la del diario, solo la de la cia del diario
            if company.currency_id != used_currency:
                currency_table[company.currency_id.id] = (
                    used_currency.rate / company.currency_id.rate)
            date_from = datetime.date.today().replace(day=1)
            date_to = date_from + relativedelta(months=1, days=-1)
            to_string = fields.Date.to_string
            report = report.with_context(
                date_from=to_string(date_from), date_to=to_string(date_to))
            # si calculamos con financial reports los importes estan en la
            # moneda del usuario
            currency = used_currency

            report_position = sum(
                [x['balance'] for x in report.line_ids.get_balance(
                    {}, currency_table, report,
                    field_names=['balance'])])

        unsettled_lines = self.env['account.move.line'].search(
            self._get_tax_settlement_lines_domain() + [
                ('tax_state', '=', 'to_settle')])

        res.update({
            # los importes estan en la moneda de la cia, sin importar el diario
            'report_position': formatLang(
                self.env, report_position, currency_obj=currency),
            'unsettled_count': len(unsettled_lines),
            'unsettled_amount': formatLang(
                self.env, sum(unsettled_lines.mapped('balance')),
                currency_obj=currency),
        })
        return res

    @api.multi
    def _get_tax_settlement_lines_domain(self):
        self.ensure_one()
        return [
            ('company_id', '=', self.company_id.id),
            ('account_id.tag_ids', 'in', self.settlement_account_tag_ids.ids),
        ]

    @api.multi
    def open_action(self):
        """
        Modificamos funcion para que si hay un reporte vinculado
        la posición muestre el reporte
        """
        if self.type == 'general' and self.settlement_tax:
            tax_settlement = self._context.get('tax_settlement', False)
            open_report = self._context.get('open_report', False)
            if tax_settlement:
                action = self.env.ref(
                    'account_tax_settlement.'
                    'action_account_tax_move_line').read()[0]
                action['domain'] = self._get_tax_settlement_lines_domain()
                # ctx = self._context.copy()
                # ctx.update({
                #     'search_default_unsettled_tax': 1,
                # })
                # action['view_id'] = self.env.ref(
                #     'account_tax_settlement.view_account_move_line_tree').id
                # action['context'] = ctx
                action['domain'] = self._get_tax_settlement_lines_domain()
                return action
            if open_report:
                if self.settlement_financial_report_id:
                    report = self.settlement_financial_report_id
                    action = self.env['ir.actions.client'].search([
                        ('name', '=', report.get_title()),
                        ('tag', '=', 'account_report_generic')], limit=1)
                    if action:
                        return action.read()[0]
        return super(AccountJournal, self).open_action()
