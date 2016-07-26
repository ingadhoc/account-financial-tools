# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields, _
# from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gral_domain = [('reconcile_id', '=', False)]
    receivable_domain = gral_domain + [('type', '=', 'receivable')]
    payable_domain = gral_domain + [('type', '=', 'payable')]

    receivable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=receivable_domain,
    )
    payable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=payable_domain,
    )
    debt_balance = fields.Float(
        compute='_get_debt_balance',
    )

    @api.multi
    def _get_debt_lines2(self):
        self.ensure_one()

        result_selection = self._context.get('result_selection', False)
        group_by_move = self._context.get('group_by_move', False)
        from_date = self._context.get('from_date', False)

        if result_selection == 'receivable':
            domain = self.receivable_domain
        elif result_selection == 'payable':
            domain = self.payable_domain
        else:
            domain = self.gral_domain
        domain += [('partner_id', '=', self.id)]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            intitial_moves = self.env['account.debt.line'].search(
                initial_domain)
            balance = sum(intitial_moves.mapped('amount'))
            financial_balance = sum(intitial_moves.mapped('financial_amount'))
            res = [{
                # 'move_id': False,
                'date': False,
                'name': _('INITIAL BALANCE'),
                'date_maturity': False,
                'amount': False,
                'balance': balance,
                'financial_amount': False,
                'financial_balance': financial_balance,
            }]
            domain.append(('date', '>=', from_date))
        else:
            balance = 0.0
            financial_balance = 0.0
            res = []

        if group_by_move:
            records = self.env['account.debt.line'].read_group(
                domain=domain,
                fields=['move_id'],
                groupby=['move_id'],
            )
        else:
            records = self.env['account.debt.line'].search(domain)

        # construimos una nueva lista con los valores que queremos y de
        # manera mas facil
        for record in records:
            print 'record', record
            if group_by_move:
                move_lines = self.env['account.debt.line'].search(
                    record.get('__domain'))
                move = self.env['account.move'].browse(
                    record.get('move_id')[0])
                date_maturity = move_lines[0].date_maturity
            else:
                move_lines = record
                date_maturity = record.date_maturity
                move = record.move_id
            amount = sum(move_lines.mapped('amount'))
            financial_amount = sum(move_lines.mapped('financial_amount'))
            balance += amount
            financial_balance += financial_amount
            res.append({
                # 'move_id': move,
                'date': move.date,
                'name': move.display_name,
                'date_maturity': date_maturity,
                'amount': amount,
                'balance': balance,
                'financial_amount': financial_amount,
                'financial_balance': financial_balance,
            })
        # print 'grouped_lines', grouped_lines
        print 'res', res
        return res

    @api.multi
    def _get_grouped_debt_lines(self):
        self.ensure_one()
        lines = self._get_debt_lines()
        grouped_lines = lines.read_group(
            domain=[('id', 'in', lines.ids)],
            fields=['move_id', 'display_name', 'name'],
            groupby=['move_id'],
        )
        res = []
        # construimos una nueva lista con los valores que queremos y de
        # manera mas facil
        balance = 0.0
        financial_balance = 0.0
        for group in grouped_lines:
            lines = self.env['account.debt.line'].search(group.get('__domain'))
            amount = sum(lines.mapped('amount'))
            financial_amount = sum(lines.mapped('financial_amount'))
            balance += amount
            financial_balance += financial_amount
            res.append({
                'move_id': self.env['account.move'].browse(
                    group.get('move_id')[0]),
                'lines': lines,
                'amount': amount,
                'balance': balance,
                'financial_amount': financial_amount,
                'financial_balance': financial_balance,
            })
        print 'grouped_lines', grouped_lines
        print 'res', res
        return res

    @api.multi
    def _get_debt_lines(self):
        self.ensure_one()
        result_selection = self._context.get('result_selection', False)
        if result_selection == 'receivable':
            domain = self.receivable_domain
        elif result_selection == 'payable':
            domain = self.payable_domain
        else:
            domain = self.gral_domain
        domain += [('partner_id', '=', self.id)]
        return self.env['account.debt.line'].search(domain)

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
