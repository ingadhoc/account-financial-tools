# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, _
from openerp.exceptions import Warning


class res_partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_str_tuple(self, list_to_convert):
        return "(" + ",".join(["'%s'" % x for x in list_to_convert]) + ")"

    @api.multi
    def get_summary_initial_amounts(self):
        self.ensure_one()
        context = self._context
        from_date = context.get('from_date', False)
        company_id = context.get('company_id', False)
        account_types = context.get('account_types')
        if not account_types:
            raise Warning(_('Account_types not in context!'))

        keys = ['debit', 'credit', 'balance']
        if not from_date:
            return dict(zip(keys, [0.0, 0.0, 0.0]))
        other_filters = " AND m.date < \'%s\'" % from_date
        if company_id:
            other_filters += " AND m.company_id = %i" % company_id

        query = """SELECT SUM(l.debit), SUM(l.credit), SUM(l.debit- l.credit)
            FROM account_move_line l
            LEFT JOIN account_account a ON (l.account_id=a.id)
            LEFT JOIN account_move m ON (l.move_id=m.id)
            WHERE a.type IN %s
            AND l.partner_id = %i
            %s
              """ % (
                self._get_str_tuple(account_types), self.id, other_filters)
        self._cr.execute(query)
        res = self._cr.fetchall()

        return dict(zip(keys, res[0]))

    @api.multi
    def get_summary_final_balance(self):
        self.ensure_one()
        context = self._context
        to_date = context.get('to_date', False)
        company_id = context.get('company_id', False)
        account_types = context.get('account_types')
        if not account_types:
            raise Warning(_('Account_types not in context!'))

        other_filters = ""
        if to_date:
            other_filters += " AND m.date < \'%s\'" % to_date
        if company_id:
            other_filters += " AND m.company_id = %i" % company_id

        query = """SELECT SUM(l.debit- l.credit)
            FROM account_move_line l
            LEFT JOIN account_account a ON (l.account_id=a.id)
            LEFT JOIN account_move m ON (l.move_id=m.id)
            WHERE a.type IN %s
            AND l.partner_id = %i
            %s
              """ % (
                self._get_str_tuple(account_types), self.id, other_filters)
        self._cr.execute(query)
        res = self._cr.fetchall()
        return res[0]

    @api.multi
    def get_summary_moves_data(self):
        self.ensure_one()

        context = self._context
        from_date = context.get('from_date', False)
        to_date = context.get('to_date', False)
        company_id = context.get('company_id', False)
        group_by_move = context.get('group_by_move', False)
        secondary_currency = context.get('secondary_currency', False)
        # secondary_currency_id = context.get('secondary_currency_id', False)
        account_types = context.get('account_types')
        if not account_types:
            raise Warning(_('Account_types not in context!'))

        other_filters = ""
        if from_date:
            other_filters += " AND m.date >= \'%s\'" % from_date
        if to_date:
            other_filters += " AND m.date <= \'%s\'" % to_date
        if company_id:
            other_filters += " AND m.company_id = %i" % company_id

        # si group_by_move entonces obtenemos el max del maturity para que
        # no desagrupe por fecha de vencimiento
        if group_by_move:
            select = """SELECT l.move_id,
            Max(l.date_maturity) as date_maturity,
            SUM(l.debit), SUM(l.credit),
            """
            group_by = (
                "GROUP BY m.date, l.move_id, l.currency_id")
        else:
            select = """SELECT l.move_id,
            l.date_maturity as date_maturity,
            SUM(l.debit), SUM(l.credit),
            """
            group_by = (
                "GROUP BY m.date, l.move_id, date_maturity, l.currency_id")
        query = """%s
            SUM(l.amount_currency) as amount_currency, l.currency_id
            FROM account_move_line l
            LEFT JOIN account_account a ON (l.account_id=a.id)
            LEFT JOIN account_move m ON (l.move_id=m.id)
            WHERE a.type IN %s
            AND l.partner_id = %i
            %s
            %s
            ORDER BY m.date ASC, date_maturity ASC
              """ % (
                select,
                self._get_str_tuple(account_types),
                self.id,
                other_filters,
                group_by)
        self._cr.execute(query)
        res = self._cr.fetchall()

        lines_vals = []
        balance = self.get_summary_initial_amounts()['balance'] or 0.0
        for line in res:
            line_balance = line[2] - line[3]
            # si se pidio una secondary currency y es igual a la de la linea
            # obtenemos el amount currency
            line_currency_id = line[5]
            amount_currency = 0.0
            line_currency = self.env['res.currency']
            if (
                    secondary_currency and line_currency_id):
                    # secondary_currency_id and
                    # secondary_currency_id == line_currency_id):
                amount_currency = line[4]
                line_currency = line_currency.browse(line_currency_id)
            if line_balance > 0:
                debit = line_balance
                credit = 0.0
            elif line_balance < 0:
                debit = 0.0
                credit = -line_balance
            elif not amount_currency:
                # if no line balance and no amount_currency, we dont print it
                continue
            balance += line_balance
            lines_vals.append({
                'move': self.env['account.move'].browse(line[0]),
                'date_maturity': line[1],
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'amount_currency': amount_currency,
                'line_currency': line_currency,
            })
        return lines_vals
