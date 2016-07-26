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
                return self.env['res.company'].search([])

    @api.multi
    def _get_debt_report_lines(self, company):
        self.ensure_one()

        result_selection = self._context.get('result_selection', False)
        group_by_move = self._context.get('group_by_move', False)
        from_date = self._context.get('from_date', False)
        unreconciled_lines = self._context.get('unreconciled_lines', False)
        company_type = self._context.get('company_type', False)
        show_invoice_detail = self._context.get('show_invoice_detail', False)
        # TODO implementar
        # show_receipt_detail = self._context.get('show_receipt_detail', False)

        domain = []

        # si no se consolida, entonces buscamos los de la cia que se pasa
        if not company_type == 'consolidate':
            domain += [('company_id', '=', company.id)]

        if unreconciled_lines:
            domain += self.unreconciled_domain

        if result_selection == 'receivable':
            domain += self.receivable_domain
        elif result_selection == 'payable':
            domain += self.payable_domain

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
                'detail': False,
                'balance': balance,
                'financial_amount': False,
                'financial_balance': financial_balance,
                'amount_currency': False,
                'currency_name': False,
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
            detail_lines = []
            if group_by_move:
                move_lines = self.env['account.debt.line'].search(
                    record.get('__domain'))
                move = self.env['account.move'].browse(
                    record.get('move_id')[0])
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
                date_maturity = record.date_maturity
                move = record.move_id
                currency = record.currency_id
            amount = sum(move_lines.mapped('amount'))
            financial_amount = sum(move_lines.mapped('financial_amount'))
            amount_currency = sum(move_lines.mapped('amount_currency'))
            balance += amount
            financial_balance += financial_amount
            res.append({
                # 'move_id': move,
                'date': move.date,
                'name': move.display_name,
                'detail_lines': detail_lines,
                'date_maturity': date_maturity,
                'amount': amount,
                'balance': balance,
                'financial_amount': financial_amount,
                'financial_balance': financial_balance,
                'amount_currency': amount_currency,
                'currency_name': currency.name,
            })
        # append final balance line
        # res.append({
        #         # 'move_id': False,
        #         'date': False,
        #         'name': _('FINAL BALANCE'),
        #         'date_maturity': False,
        #         'amount': False,
        #         'balance': balance,
        #         'financial_amount': False,
        #         'financial_balance': financial_balance,
        #         'amount_currency': False,
        #         'currency_name': False,
        #     }]
        return res

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
