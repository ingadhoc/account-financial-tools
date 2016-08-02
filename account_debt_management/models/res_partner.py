# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields, _
# from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    unreconciled_domain = [('reconcile_id', '=', False)]
    receivable_domain = [('type', '=', 'receivable')]
    payable_domain = [('type', '=', 'payable')]

    receivable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=unreconciled_domain + receivable_domain,
    )
    payable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=unreconciled_domain + payable_domain,
    )
    debt_balance = fields.Float(
        compute='_get_debt_balance',
    )

    @api.multi
    def _get_debt_report_companies(self):
        """
        Si se especifica una compañia devolvemos esa, si no, si:
        * se agrupa por compania, entonces devolvemos cia del usuario para
        simlemente devolver algo
        * si no se agrupa, devolvemos todas las cias que podemos ver
        """
        self.ensure_one()
        company_type = self._context.get('company_type', False)
        company_id = self._context.get('company_id', False)
        company = self.env['res.company'].browse(company_id)
        if company:
            return company
        else:
            if company_type == 'consolidate':
                return self.env.user.company_id
            # group_by_company
            else:
                # we only want companies that have moves for this partner
                records = self.env['account.debt.line'].read_group(
                    domain=[('partner_id', '=', self.id)],
                    fields=['company_id'],
                    groupby=['company_id'],
                )
                company_ids = []
                for record in records:
                    company_ids.append(record['company_id'][0])
                return self.env['res.company'].browse(company_ids)

    @api.multi
    def _get_debt_report_lines(self, company):
        def get_line_vals(
                date=False, name=False, detail_lines=[], date_maturity=False,
                amount=False, balance=False, financial_amount=False,
                financial_balance=False, amount_currency=False,
                currency_name=False):
            return {
                'date': date,
                'name': name,
                'detail_lines': detail_lines,
                'date_maturity': date_maturity,
                'amount': amount,
                'balance': balance,
                'financial_amount': financial_amount,
                'financial_balance': financial_balance,
                'amount_currency': amount_currency,
                'currency_name': currency_name,
            }

        self.ensure_one()

        result_selection = self._context.get('result_selection', False)
        group_by_move = self._context.get('group_by_move', False)
        from_date = self._context.get('from_date', False)
        to_date = self._context.get('to_date', False)
        historical_full = self._context.get('historical_full', False)
        company_type = self._context.get('company_type', False)
        show_invoice_detail = self._context.get('show_invoice_detail', False)
        # TODO implementar
        # show_receipt_detail = self._context.get('show_receipt_detail', False)

        domain = []

        # si no se consolida, entonces buscamos los de la cia que se pasa
        if not company_type == 'consolidate':
            domain += [('company_id', '=', company.id)]

        if not historical_full:
            domain += self.unreconciled_domain

        if result_selection == 'receivable':
            domain += self.receivable_domain
        elif result_selection == 'payable':
            domain += self.payable_domain

        domain += [('partner_id', '=', self.id)]

        without_date_domain = domain[:]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            intitial_moves = self.env['account.debt.line'].search(
                initial_domain)
            balance = sum(intitial_moves.mapped('amount'))
            financial_balance = sum(intitial_moves.mapped('financial_amount'))
            res = [get_line_vals(
                name=_('INITIAL BALANCE'), balance=balance,
                financial_balance=financial_balance)]
            domain.append(('date', '>=', from_date))
        else:
            balance = 0.0
            financial_balance = 0.0
            res = []

        if to_date:
            all_moves = self.env['account.debt.line'].search(
                without_date_domain)
            balance = sum(all_moves.mapped('amount'))
            financial_balance = sum(all_moves.mapped('financial_amount'))
            final_line = [get_line_vals(
                name=_('FINAL BALANCE'), balance=balance,
                financial_balance=financial_balance)]
            domain.append(('date', '<=', to_date))
        else:
            final_line = []

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
            detail_lines = []
            if group_by_move:
                move_lines = self.env['account.debt.line'].search(
                    record.get('__domain'))
                move = self.env['account.move'].browse(
                    record.get('move_id')[0])
                display_names = move_lines.mapped('display_name')
                display_names = list(set(display_names))
                date = move.date
                # si todos los display names de lineas son iguales, mostramos
                # eso, si no, el del move
                if len(display_names) == 1:
                    display_name = display_names[0]
                else:
                    display_name = move.display_name
                date_maturity = move_lines[0].date_maturity
                # TODO podrian existir distintas monedas en asientos manuales
                # arreglar
                currency = move_lines[0].currency_id
                if show_invoice_detail:
                    for inv_line in move_lines.mapped(
                            'move_line_id.invoice.invoice_line'):
                        detail_lines.append(
                            ("* %s x %s %s" % (
                                inv_line.name.replace(
                                    '\n', ' ').replace('\r', ''),
                                inv_line.quantity,
                                inv_line.uos_id.name)))
            else:
                move_lines = record
                display_name = record.display_name
                date_maturity = record.date_maturity
                # no tomamos el date del move, si bien este es un campo
                # related, porque algunas veces hacen el artilugio de cambiar
                # esta fecha en el move line
                date = record.date
                move = record.move_id
                currency = record.currency_id
            amount = sum(move_lines.mapped('amount'))
            financial_amount = sum(move_lines.mapped('financial_amount'))
            amount_currency = sum(move_lines.mapped('amount_currency'))
            balance += amount
            financial_balance += financial_amount
            res.append(get_line_vals(
                date=date,
                name=display_name,
                detail_lines=detail_lines,
                date_maturity=date_maturity,
                amount=amount, balance=balance,
                financial_amount=financial_amount,
                financial_balance=financial_balance,
                amount_currency=amount_currency,
                currency_name=currency.name,
            ))
        res += final_line
        return res

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
