##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class ResCompanyInterest(models.Model):

    _name = 'res.company.interest'
    _description = 'Account Interest'

    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        ondelete='cascade',
    )
    receivable_account_ids = fields.Many2many(
        'account.account',
        string='Cuentas a Cobrar',
        help='Cuentas a Cobrar que se tendrán en cuenta para evaular la deuda',
        required=True,
        domain=lambda self: [('account_type', '=', 'asset_receivable'),
                             ('company_id', '=', self._context.get('default_company_id') or self.env.company.id)],
    )
    interest_product_id = fields.Many2one(
        'product.product',
        'Interest Product',
        required=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        'Analytic account',
    )
    rate = fields.Float(
        'Interest',
        required=True,
        digits=(7, 4)
    )
    automatic_validation = fields.Boolean(
        'Automatic Validation?',
        help='Automatic Invoice Validation?',
        default=True,
    )
    rule_type = fields.Selection([
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('yearly', 'Year(s)'),
    ],
        'Recurrency',
        help="Interests Invoice automatically repeat at specified interval",
        default='monthly',
    )
    interval = fields.Integer(
        'Repeat Every',
        default=1,
        help="Repeat every (Days/Week/Month/Year)"
    )
    next_date = fields.Date(
        'Date of Next Invoice',
        default=fields.Date.today,
    )
    domain = fields.Char(
        'Additional Filters',
        default="[]",
        help="Extra filters that will be added to the standard search"
    )
    has_domain = fields.Boolean(compute="_compute_has_domain")

    late_payment_interest = fields.Boolean('Late payment interest', default=False, help="The interest calculation takes into account all late payments from the previous period. To obtain the daily rate, the interest is divided by the period. These days are considered depending on the type of period: 360 for annual, 30 for monthly and 7 for weekly.")

    @api.model
    def _cron_recurring_interests_invoices(self):
        _logger.info('Running Interest Invoices Cron Job')
        current_date = fields.Date.today()
        companies_with_errors = []

        for rec in self.search([('next_date', '<=', current_date)]):
            try:
                rec.create_interest_invoices()
                rec.env.cr.commit()
            except:
                _logger.error('Error creating interest invoices for company: %s', rec.company_id.name)
                companies_with_errors.append(rec.company_id.name)
                rec.env.cr.rollback()

        if companies_with_errors:
            company_names = ', '.join(companies_with_errors)
            error_message = _("We couldn't run interest invoices cron job in the following companies: %s.") % company_names
            raise UserError(error_message)

    def create_interest_invoices(self):
        for rec in self:
            _logger.info(
                'Creating Interest Invoices (id: %s, company: %s)', rec.id,
                rec.company_id.name)
            # hacemos un commit para refrescar cache
            self.env.cr.commit()
            to_date = rec.next_date

            rule_type = rec.rule_type
            interval = rec.interval

            if rule_type == 'daily':
                next_delta = relativedelta(days=+interval)
                from_date_delta = relativedelta(days=-interval)
            elif rule_type == 'weekly':
                next_delta = relativedelta(weeks=+interval)
                from_date_delta = relativedelta(weeks=-interval)
            elif rule_type == 'monthly':
                next_delta = relativedelta(months=+interval)
                from_date_delta = relativedelta(months=-interval)
            else:
                next_delta = relativedelta(years=+interval)
                from_date_delta = relativedelta(years=-interval)

            from_date = to_date + from_date_delta

            # llamamos a crear las facturas con la compañia del interes para
            # que tome correctamente las cuentas
            rec.with_company(rec.company_id).with_context(default_l10n_ar_afip_asoc_period_start=from_date,
                             default_l10n_ar_afip_asoc_period_end=to_date).create_invoices(from_date, to_date)

            # seteamos proxima corrida en hoy mas un periodo
            rec.next_date = to_date + next_delta

    def _get_move_line_domains(self):
        self.ensure_one()
        move_line_domain = [
            ('account_id', 'in', self.receivable_account_ids.ids),
            ('partner_id.active', '=', True),
            ('parent_state', '=', 'posted'),
        ]
        return move_line_domain

    def create_invoices(self, from_date, to_date, groupby=['partner_id']):
        """
        tengo deudas viejas por 2000 (super viejas)
        el 1 facturo 1000 que vencen el 20
        el 25 pagó 400.
        Detalle de cálculo de intereses:
            * interés por todo lo viejo (2000) x el rate
            * interés de todo lo que venció en el último período ($600) x días que estuvo vencido (10 días)
            * si además marcó "latest payment intereset" se agrega interés por los días que pagó tarde, es decir $400 x 5 días
        """
        self.ensure_one()

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)], limit=1)

        if self.receivable_account_ids != journal.default_account_id:
            journal = self.env['account.journal'].search([('default_account_id','in',self.receivable_account_ids.ids)], limit=1) or journal

        # vemos todo lo impago que vencia antes del comienzo de este periodo de intereses ya que el interes ahí se calcula sobre el total
        # entre from date y to_date tenemos que calcular parciales segun dias cuando vencia comprobante
        move_line_domain_previous_periods = self._get_move_line_domains() + [('full_reconcile_id', '=', False), ('date_maturity', '<', from_date)]
        # Check if a filter is set
        if self.domain:
            move_line_domain_previous_periods += safe_eval(self.domain)

        # fields = ['id:recordset', 'amount_residual:sum', 'partner_id:recordset', 'account_id:recordset'] descarto esto porque ya no se estan usando la mayoria de valores
        fields = ['amount_residual:sum']

        move_line = self.env['account.move.line']
        # DE ACA VAN A SALIR LAS LINES DE DEUDAS ANTERIORES
        previous_grouped_lines = move_line._read_group(
            domain=move_line_domain_previous_periods,
            groupby=groupby,
            aggregates=fields,
        )

        deuda = {x[0]: {'Deuda periodos anteriores': x[1] * self.rate} for x in previous_grouped_lines}

        interest_rate = {
            'daily': 1,
            'weekly': 7,
            'monthly': 30,
            'yearly': 360,
        }

        # calculamos intereses de facturas
        last_period_lines = move_line.search(self._get_move_line_domains() + [('amount_residual', '>', 0), ('date_maturity', '>=', from_date), ('date_maturity', '<', to_date)])
        for partner, amls in last_period_lines.grouped('partner_id').items():
            interest = 0
            for move, lines in amls.grouped('move_id').items():
                days = (to_date - move.invoice_date_due).days
                interest += move.amount_residual * days * (self.rate / interest_rate[self.rule_type])
            # dias de vencimiento
            # TODO completar y tmb sumar a las grouped lines
            # hacer que se acumulan
            # (to_date - move_line.date_maturity) * rate de vencimiento

            # agregamos a la deuda antigua
            if partner in deuda:
                deuda[partner]['Deuda último periodo'] = interest
            else:
                deuda[partner] = {'Deuda último periodo': interest}


        # Feature de intereses por pago tardio (periodo actual)
        # ToDo comentar esta funcionalidad
        if self.late_payment_interest:
            # #last_period_lines_domain = self._get_move_line_domains() + [('date_maturity', '>=', to_date)]

            partials = self.env['account.partial.reconcile'].search([
                ('debit_move_id.partner_id.active', '=', True),
                ('debit_move_id.date_maturity', '>=', from_date),
                ('debit_move_id.date_maturity', '<=', to_date),
                ('debit_move_id.parent_state', '=', 'posted'),
                    # lo dejamos para NTH
                    # debit_move_id. safe eval domain
                ('debit_move_id.account_id', 'in', self.receivable_account_ids.ids),
                ('credit_move_id.date', '>=', from_date),
                ('credit_move_id.date', '<', to_date)]).grouped('debit_move_id')

            for move_line, parts in partials.items():
                due_payments = parts.filtered(lambda x: x.credit_move_id.date > x.debit_move_id.date_maturity)
                if due_payments:
                    due_payments_amount = sum(due_payments.mapped('amount'))
                    last_date_payment = parts.filtered(lambda x: x.credit_move_id.date > x.debit_move_id.date_maturity).sorted('max_date')[-1].max_date
                    days = (last_date_payment - move_line.date_maturity).days
                    interest += due_payments_amount * days * (self.rate / interest_rate[self.rule_type])
                    partner = move_line.partner_id
                    if partner in deuda and 'Deuda pagos vencidos' in deuda[partner]:
                        deuda[partner]['Deuda pagos vencidos'] += interest
                    elif partner in deuda:
                        deuda[partner]['Deuda pagos vencidos'] = interest
                    else:
                        deuda[partner] = {'Deuda pagos vencidos': interest}

        self = self.with_context(
            company_id=self.company_id.id,
            mail_notrack=True,
            prefetch_fields=False).with_company(self.company_id)

        total_items = len(deuda)
        _logger.info('%s interest invoices will be generated', total_items)
        for idx, lines in enumerate(deuda):
            move_vals = self._prepare_interest_invoice(
                lines, to_date, journal)

            if not move_vals:
                continue

            _logger.info('Creating Interest Invoice (%s of %s) with values:\n%s', idx + 1, total_items, line)

            move = self.env['account.move'].create(move_vals)

            if self.automatic_validation:
                try:
                    move.action_post()
                except Exception as e:
                    _logger.error(
                        "Something went wrong creating "
                        "interests invoice: {}".format(e))



    def prepare_info(self, to_date, debt):
        self.ensure_one()

        # Format date to customer language
        lang_code = self.env.context.get('lang', self.env.user.lang)
        lang = self.env['res.lang']._lang_get(lang_code)
        date_format = lang.date_format
        to_date_format = to_date.strftime(date_format)

        res = _(
            'Deuda Vencida al %s: %s\n'
            'Tasa de interés: %s') % (
                to_date_format, debt, self.rate)

        return res

    def _prepare_interest_invoice(self, lines, to_date, journal, forced_interest_amount=False):
        self.ensure_one()
        # ADAPTAR LINES
        line = lines
        debt = line[2]

        if (not debt or debt <= 0.0) and not forced_interest_amount:
            _logger.info("Debt is negative, skipping...")
            return

        partner_id = line[0].id
        partner = self.env['res.partner'].browse(partner_id)
        comment = self.prepare_info(to_date, debt) if not forced_interest_amount else 'Deuda Vencida por Pago Atrasado'
        fpos = partner.property_account_position_id
        taxes = self.interest_product_id.taxes_id.filtered(
            lambda r: r.company_id == self.company_id)
        tax_id = fpos.map_tax(taxes)
        invoice_vals = {
            'move_type': 'out_invoice',
            'currency_id': self.company_id.currency_id.id,
            'partner_id': partner.id,
            'fiscal_position_id': fpos.id,
            'user_id': partner.user_id.id or False,
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'invoice_origin': "Interests Invoice",
            'narration': self.interest_product_id.name + '.\n' + comment,
            'invoice_line_ids': [(0, 0, {
                "product_id": self.interest_product_id.id,
                "quantity": 1.0,
                "price_unit": self.rate * debt if not forced_interest_amount else forced_interest_amount,
                "partner_id": partner.id,
                "name": self.interest_product_id.name + '.\n' + comment,
                "analytic_distribution": {self.analytic_account_id.id: 100.0} if self.analytic_account_id.id else False,
                "tax_ids": [(6, 0, tax_id.ids)]
            })],
        }

        # hack para evitar modulo glue con l10n_latam_document
        if journal._fields.get('l10n_latam_use_documents') and journal.l10n_latam_use_documents:
            debit_note = self.env['account.move'].new({
                'move_type': 'out_invoice',
                'journal_id': journal.id,
                'partner_id': partner.id,
                'company_id': self.company_id.id,
            })
            document_types = debit_note.l10n_latam_available_document_type_ids.filtered(lambda x: x.internal_type == 'debit_note')
            invoice_vals['l10n_latam_document_type_id'] = document_types and document_types[0]._origin.id or debit_note.l10n_latam_document_type_id.id

        return invoice_vals

    @api.depends('domain')
    def _compute_has_domain(self):
        for rec in self:
            rec.has_domain = len(safe_eval(rec.domain)) > 0
