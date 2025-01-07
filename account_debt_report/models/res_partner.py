##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, _
from odoo.tools.safe_eval import safe_eval
# from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_debt_report_wizard(self):

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.debt.report.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('account_debt_report.account_debt_report_wizard_form').id,
            'target': 'new',
            'context': {
                'partner_id': self.id,
            },
        }

    def _get_debt_report_lines(self):
        # TODO ver si borramos este metodo que no tiene mucho sentido (get_line_vals)
        def get_line_vals(
                date=None, name=None, detail_lines=None, date_maturity=None,
                amount=None, amount_residual=None, balance=None,
                amount_currency=None,
                currency_name=None, move_line=None):
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
                'amount_currency': amount_currency,
                'currency_name': currency_name,
                'move_line': move_line,
            }

        self.ensure_one()

        result_selection = self._context.get('result_selection', False)
        from_date = self._context.get('from_date', False)
        to_date = self._context.get('to_date', False)
        historical_full = self._context.get('historical_full', False)
        company_id = self._context.get('company_id', False)
        show_invoice_detail = self._context.get('show_invoice_detail', False)
        only_currency_lines = not self._context.get('company_currency') and self._context.get('secondary_currency')
        balance_in_currency = 0.0
        balance_in_currency_name = ''
        domain = []

        if company_id:
            domain += [('company_id', '=', company_id)]
            company_currency_ids = self.env['res.company'].browse(company_id).currency_id
        else:
            domain += [('company_id', 'in', self.env.companies.ids)]
            company_currency_ids = self.env.companies.mapped('currency_id')
        if only_currency_lines and len(company_currency_ids) == 1:
            domain += [('currency_id', 'not in', company_currency_ids.ids)]

        if not historical_full:
            domain += [('reconciled', '=', False), ('full_reconcile_id', '=', False)]
            # si pide historial completo entonces mostramos los movimientos
            # si no mostramos los saldos
            balance_field = 'amount_residual'
        else:
            balance_field = 'balance'

        if result_selection == 'receivable':
            domain += [('account_type', '=', 'asset_receivable')]
        elif result_selection == 'payable':
            domain += [('account_type', '=', 'liability_payable')]
        else:
            domain += [('account_type', 'in', ['asset_receivable', 'liability_payable'])]

        domain += [('partner_id', '=', self.id), ('parent_state', '=', 'posted')]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            inicial_lines = self.env['account.move.line'].sudo()._read_group(
                initial_domain, groupby=['partner_id'], aggregates=['balance:sum'])
            balance = inicial_lines[0][1] if inicial_lines else 0.0
            if len(company_currency_ids) == 1:
                inicial_lines_currency = self.env['account.move.line'].sudo()._read_group(
                    initial_domain + [('currency_id', 'not in', company_currency_ids.ids)], groupby=['partner_id'], aggregates=['amount_currency:sum', 'currency_id:array_agg'])
                balance_in_currency = inicial_lines_currency[0][1] if inicial_lines_currency else 0.0
                balance_in_currency_name = self.env['res.currency'].browse(inicial_lines_currency[0][2][0]).display_name if inicial_lines_currency and inicial_lines_currency[0][2][0] else  ''
            res = [get_line_vals(name=_('INITIAL BALANCE'), balance=balance, amount_currency=balance_in_currency, currency_name=balance_in_currency_name)]
            domain.append(('date', '>=', from_date))
        else:
            balance = 0.0
            res = []

        if to_date:
            domain.append(('date', '<=', to_date))
        final_line = []

        records = self.env['account.move.line'].sudo().search(domain, order='date asc, name, move_id desc, date_maturity asc, id')

        # construimos una nueva lista con los valores que queremos y de
        # manera mas facil
        for record in records:
            detail_lines = []
            if show_invoice_detail:
                for inv_line in record.move_id.invoice_line_ids:
                    inv_line_name = inv_line.name or "Sin descripción"
                    inv_line_product_uom_id_name = inv_line.product_uom_id.name or "Sin unidad de medida"
                    detail_lines.append(
                        ("* %s x %s %s" % (
                            inv_line_name.replace(
                                '\n', ' ').replace('\r', ''),
                            inv_line.quantity,
                            inv_line_product_uom_id_name)))
            name = record.move_id.name
            # similar to _format_aml_name
            if record.ref and record.ref != '/':
                name += ' - ' + record.ref

            date_maturity = record.date_maturity
            date = record.date
            currency = record.currency_id
            balance += record[balance_field]
            amount = record.balance
            amount_residual = record.amount_residual
            amount_currency = record.amount_currency
            show_currency = record.currency_id != record.company_id.currency_id
            if record.payment_id:
                name += ' - ' + record.journal_id.name

            # TODO tal vez la suma podriamos probar hacerla en el xls como hacemos en libro iva v11/v12
            res.append(get_line_vals(
                date=date,
                name=name,
                detail_lines=detail_lines,
                date_maturity=date_maturity,
                amount=amount,
                amount_residual=amount_residual,
                balance=balance,
                amount_currency=amount_currency if show_currency else False,
                currency_name=currency.name if show_currency else False,
                # move_line=record.move_line_id,
            ))

        record_currencys = records.filtered(lambda x: x.currency_id != x.company_id.currency_id)
        if len(record_currencys.mapped('currency_id')) == 1:
            total_currency = sum(record_currencys.mapped('amount_currency')) + balance_in_currency
            final_line += [get_line_vals(name=_('Total'), amount_currency=total_currency, currency_name=record_currencys.mapped('currency_id').name)]

        res += final_line
        return res
