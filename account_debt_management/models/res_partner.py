##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models, fields, _
# from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    unreconciled_domain = [('reconciled', '=', False)]
    receivable_domain = [('internal_type', '=', 'receivable')]
    payable_domain = [('internal_type', '=', 'payable')]

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
    debt_balance = fields.Monetary(
        compute='_compute_debt_balance',
        currency_field='currency_id',
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
                date=None, name=None, detail_lines=None, date_maturity=None,
                amount=None, amount_residual=None, balance=None,
                financial_amount=None, financial_amount_residual=None,
                financial_balance=None,
                amount_currency=None,
                currency_name=None):
            if not detail_lines:
                detail_lines = []
            return {
                'date': date,
                'name': name,
                'detail_lines': detail_lines,
                'date_maturity': date_maturity,
                'amount': amount,
                'amount_residual': amount_residual,
                'balance': balance,
                'financial_amount': financial_amount,
                'financial_amount_residual': financial_amount_residual,
                'financial_balance': financial_balance,
                'amount_currency': amount_currency,
                'currency_name': currency_name,
            }

        self.ensure_one()

        result_selection = self._context.get('result_selection', False)
        from_date = self._context.get('from_date', False)
        to_date = self._context.get('to_date', False)
        historical_full = self._context.get('historical_full', False)
        company_type = self._context.get('company_type', False)
        show_invoice_detail = self._context.get('show_invoice_detail', False)

        domain = []

        # si no se consolida, entonces buscamos los de la cia que se pasa
        if not company_type == 'consolidate':
            domain += [('company_id', '=', company.id)]

        if not historical_full:
            domain += self.unreconciled_domain
            # si pide historial completo entonces mostramos los movimientos
            # si no mostramos los saldos
            balance_field = 'amount_residual'
            financial_balance_field = 'financial_amount_residual'
        else:
            balance_field = 'amount'
            financial_balance_field = 'financial_amount'

        if result_selection == 'receivable':
            domain += self.receivable_domain
        elif result_selection == 'payable':
            domain += self.payable_domain

        domain += [('partner_id', '=', self.id)]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            intitial_moves = self.env['account.debt.line'].search(
                initial_domain)
            balance = sum(intitial_moves.mapped(balance_field))
            financial_balance = sum(intitial_moves.mapped(
                financial_balance_field))
            res = [get_line_vals(
                name=_('INITIAL BALANCE'),
                balance=balance,
                financial_balance=financial_balance)]
            domain.append(('date', '>=', from_date))
        else:
            balance = 0.0
            financial_balance = 0.0
            res = []

        if to_date:
            # por ahora no imprimimos la linea final, solo imprimios hasta la
            # fecha en que se solicita el reporte y cambiamos para que salga
            # hasta esa fecha en el header
            # si queremos usar esto deberiamos ver que se interprete bien
            # all_moves = self.env['account.debt.line'].search(
            #     without_date_domain)
            # final_balance = sum(all_moves.mapped('amount'))
            # final_financial_balance = sum(
            #     all_moves.mapped('financial_amount'))
            # final_line = [get_line_vals(
            #     name=_('FINAL BALANCE'),
            #     balance=final_balance,
            #     financial_balance=final_financial_balance)]
            final_line = []
            domain.append(('date', '<=', to_date))
        else:
            final_line = []

        records = self.env['account.debt.line'].search(domain)

        # construimos una nueva lista con los valores que queremos y de
        # manera mas facil
        for record in records:
            detail_lines = []
            if show_invoice_detail:
                for inv_line in record.move_line_ids.mapped(
                        'invoice_id.invoice_line_ids'):
                    detail_lines.append(
                        ("* %s x %s %s" % (
                            inv_line.name.replace(
                                '\n', ' ').replace('\r', ''),
                            inv_line.quantity,
                            inv_line.uom_id.name)))
            document_number = record.document_number
            date_maturity = record.date_maturity
            date = record.date
            currency = record.currency_id
            amount = record.amount
            amount_residual = record.amount_residual
            financial_amount = record.financial_amount
            financial_amount_residual = record.financial_amount_residual
            amount_currency = record.amount_currency

            balance += record[balance_field]
            financial_balance += record[financial_balance_field]
            res.append(get_line_vals(
                date=date,
                name=document_number,
                detail_lines=detail_lines,
                date_maturity=date_maturity,
                amount=amount,
                amount_residual=amount_residual,
                balance=balance,
                financial_amount=financial_amount,
                financial_amount_residual=financial_amount_residual,
                financial_balance=financial_balance,
                amount_currency=amount_currency,
                currency_name=currency.name,
            ))
        res += final_line
        return res

    @api.multi
    # This computes makes fields to be computed upon partner creation where no
    # id exists yet and raise an erro because of partner where being empty on
    # _credit_debit_get method, ase debit and credit don't have depends, this
    # field neither
    # @api.depends('debit', 'credit')
    def _compute_debt_balance(self):
        for rec in self:
            rec.debt_balance = rec.credit - rec.debit
