##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models, fields, _
# from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

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
                records = self.env['account.move.line'].read_group(
                    domain=[('partner_id', '=', self.id)],
                    fields=['company_id'],
                    groupby=['company_id'],
                )
                company_ids = []
                for record in records:
                    company_ids.append(record['company_id'][0])
                return self.env['res.company'].browse(company_ids)

    def _get_debt_report_lines(self, company):
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
        company_type = self._context.get('company_type', False)
        show_invoice_detail = self._context.get('show_invoice_detail', False)

        domain = []

        # si no se consolida, entonces buscamos los de la cia que se pasa
        if not company_type == 'consolidate':
            domain += [('company_id', '=', company.id)]

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

        domain += [('partner_id', '=', self.id)]

        if from_date:
            initial_domain = domain + [('date', '<', from_date)]
            intitial_moves = self.env['account.move.line'].search(
                initial_domain)
            balance = sum(intitial_moves.mapped(balance_field))
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

        records = self.env['account.move.line'].search(domain)

        # construimos una nueva lista con los valores que queremos y de
        # manera mas facil
        for record in records:
            detail_lines = []
            if show_invoice_detail:
                for inv_line in record.move_id.invoice_line_ids:
                    detail_lines.append(
                        ("* %s x %s %s" % (
                            inv_line.name.replace(
                                '\n', ' ').replace('\r', ''),
                            inv_line.quantity,
                            inv_line.product_uom_id.name)))
            name = record.move_id.name
            # similar to _format_aml_name
            if record.ref and record.ref != '/':
                name += ' - ' + record.ref
            # if it's a payment we add journal name
            if record.payment_id:
                name += ' - ' + record.journal_id.name
            date_maturity = record.date_maturity
            date = record.date
            currency = record.currency_id
            amount = record.balance
            amount_residual = record.amount_residual
            amount_currency = record.amount_currency

            balance += record[balance_field]
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
