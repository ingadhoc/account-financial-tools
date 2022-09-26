##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models, fields, _
from odoo.tools.safe_eval import safe_eval
# from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

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

        domain = []

        if company_id:
            domain += [('company_id', '=', company_id)]
        else:
            domain += [('company_id', 'in', self.env.companies.ids)]

        if not historical_full:
            domain += [('reconciled', '=', False), ('full_reconcile_id', '=', False)]
            # si pide historial completo entonces mostramos los movimientos
            # si no mostramos los saldos
            balance_field = 'amount_residual'
        else:
            balance_field = 'balance'

        if result_selection == 'receivable':
            domain += [('account_internal_type', '=', 'receivable')]
        elif result_selection == 'payable':
            domain += [('account_internal_type', '=', 'payable')]
        else:
            domain += [('account_internal_type', 'in', ['receivable', 'payable'])]

        domain += [('partner_id', '=', self.id), ('parent_state', '=', 'posted')]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            inicial_lines = self.env['account.move.line'].sudo().read_group(
                initial_domain, fields=['balance'], groupby=['partner_id'])
            balance = inicial_lines[0]['balance'] if inicial_lines else 0.0
            res = [get_line_vals(name=_('INITIAL BALANCE'), balance=balance)]
            domain.append(('date', '>=', from_date))
        else:
            balance = 0.0
            res = []

        if to_date:
            final_line = []
            domain.append(('date', '<=', to_date))
        else:
            final_line = []

        records = self.env['account.move.line'].sudo().search(domain, order='date asc, name, move_id desc, date_maturity asc, id')

        grouped = self.env['account.payment']._fields.get('payment_group_id') and safe_eval(
            self.env['ir.config_parameter'].sudo().get_param(
                'account_debt_report.group_payment_group_payments', 'False'))

        last_payment_group_id = False

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

            if grouped and record.payment_id and record.payment_id.payment_group_id == last_payment_group_id:
                # si agrupamos pagos y el grupo de pagos coincide con el último, entonces acumulamos en linea anterior
                res[-1].update({
                    'amount': res[-1]['amount'] + record.balance,
                    'amount_residual': res[-1]['amount_residual'] + record.amount_residual,
                    'amount_currency': res[-1]['amount_currency'] + record.amount_currency,
                    'balance': balance,
                })
                continue
            elif grouped and record.payment_id and record.payment_id.payment_group_id != last_payment_group_id:
                # si es un payment pero no es del payment group anterior, seteamos este como ultimo payment group
                last_payment_group_id = record.payment_id.payment_group_id
            elif not grouped and record.payment_id:
                # si no agrupamos y es pago, agregamos nombre de diario para que sea mas claro
                name += ' - ' + record.journal_id.name
            elif not record.payment_id:
                last_payment_group_id = False

            # TODO tal vez la suma podriamos probar hacerla en el xls como hacemos en libro iva v11/v12
            res.append(get_line_vals(
                date=date,
                name=name,
                detail_lines=detail_lines,
                date_maturity=date_maturity,
                amount=amount,
                amount_residual=amount_residual,
                balance=balance,
                amount_currency=amount_currency,
                currency_name=currency.name,
                # move_line=record.move_line_id,
            ))
        res += final_line
        return res
