##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


class ResCompanyInterest(models.Model):

    _name = 'res.company.interest'

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
        domain="[('user_type_id.type', '=', 'receivable'),"
        "('company_id', '=', company_id)]",
    )
    invoice_receivable_account_id = fields.Many2one(
        'account.account',
        string='Invoice Receivable Account',
        help='If no account is sellected, then partner receivable account is '
        'used',
        domain="[('user_type_id.type', '=', 'receivable'),"
        "('company_id', '=', company_id)]",
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
    tolerance_interval = fields.Integer(
        'Tolerance',
        default=1,
        help="Number of periods of tolerance for dues. 0 = no tolerance"
    )
    next_date = fields.Date(
        'Date of Next Invoice',
        default=fields.Date.today,
    )

    @api.model
    def _cron_recurring_interests_invoices(self):
        _logger.info('Running interests invoices cron')
        current_date = fields.Date.today()
        self.search([
            ('next_date', '<=', current_date)]).create_interest_invoices()

    @api.multi
    def create_interest_invoices(self):
        if not self:
            return

        self.ensure_one()
        _logger.info('Creating Interests id %s', self.id)
        interests_date = self.next_date

        rule_type = self.rule_type
        interval = self.interval
        tolerance_interval = self.tolerance_interval
        # next_date = fields.Date.from_string(interests_date)
        if rule_type == 'daily':
            next_delta = relativedelta(days=+interval)
            tolerance_delta = relativedelta(days=+tolerance_interval)
        elif rule_type == 'weekly':
            next_delta = relativedelta(weeks=+interval)
            tolerance_delta = relativedelta(weeks=+tolerance_interval)
        elif rule_type == 'monthly':
            next_delta = relativedelta(months=+interval)
            tolerance_delta = relativedelta(months=+tolerance_interval)
        else:
            next_delta = relativedelta(years=+interval)
            tolerance_delta = relativedelta(years=+tolerance_interval)
        interests_date_date = fields.Date.from_string(interests_date)
        # buscamos solo facturas que vencieron antes de hoy menos un periodo
        # TODO ver si queremos que tambien se calcule interes proporcional para
        # lo que vencio en este ultimo periodo
        to_date = fields.Date.to_string(interests_date_date - tolerance_delta)

        self.create_invoices(to_date)

        # seteamos proxima corrida en hoy mas un periodo
        self.next_date = fields.Date.to_string(
            interests_date_date + next_delta)

    @api.multi
    def create_invoices(self, to_date):
        self.ensure_one()

        # Format date to customer langague
        # For some reason there is not context pass, not lang, so we
        # force it here
        lang_code = self.env.context.get('lang', self.env.user.lang)
        lang = self.env['res.lang']._lang_get(lang_code)
        date_format = lang.date_format
        to_date_format = fields.Date.from_string(
            to_date).strftime(date_format)

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)], limit=1)

        move_line_domain = [
            ('account_id', 'in', self.receivable_account_ids.ids),
            ('full_reconcile_id', '=', False),
            ('date_maturity', '<', to_date)
        ]
        move_line = self.env['account.move.line']
        grouped_lines = move_line.read_group(
            domain=move_line_domain,
            fields=['id', 'amount_residual', 'partner_id', 'account_id'],
            groupby=['partner_id'],
        )
        self = self.with_context(mail_notrack=True, prefetch_fields=False)

        for line in grouped_lines:
            debt = line['amount_residual']

            if not debt or debt <= 0.0:
                continue

            _logger.info('Creating Interest Invoices for values:\n%s', line)
            partner_id = line['partner_id'][0]

            partner = self.env['res.partner'].browse(partner_id)
            invoice_vals = self._prepare_interest_invoice(
                partner, debt, to_date, journal)

            # we send document type for compatibility with argentinian
            # invoices
            invoice = self.env['account.invoice'].with_context(
                internal_type='debit_note').create(invoice_vals)

            invoice.invoice_line_ids.create(
                self._prepare_interest_invoice_line(
                    invoice, partner, debt, to_date_format))

            # update amounts for new invoice
            invoice.compute_taxes()
            if self.automatic_validation:
                invoice.action_invoice_open()

    @api.multi
    def prepare_info(self, to_date_format, debt):
        self.ensure_one()

        res = _(
            'Deuda Vencida al %s: %s\n'
            'Tasa de interés: %s') % (
                to_date_format, debt, self.rate)

        return res

    @api.multi
    def _prepare_interest_invoice(self, partner, debt, to_date, journal):
        self.ensure_one()

        comment = self.prepare_info(to_date, debt)

        if self.invoice_receivable_account_id:
            account_id = self.invoice_receivable_account_id.id
        else:
            account_id = partner.property_account_receivable_id.id

        invoice_vals = {
            'type': 'out_invoice',
            'account_id': account_id,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'name': self.interest_product_id.name,
            'comment': comment,
            'currency_id': self.company_id.currency_id.id,
            'payment_term_id': partner.property_payment_term_id.id or False,
            'fiscal_position_id': partner.property_account_position_id.id,
            'date_invoice': self.next_date,
            'company_id': self.company_id.id,
            'user_id': partner.user_id.id or False
        }
        return invoice_vals

    @api.multi
    def _prepare_interest_invoice_line(self, invoice, partner, debt, to_date):
        self.ensure_one()
        company = self.company_id
        amount = self.rate * debt
        line_data = self.env['account.invoice.line'].with_context(
            # TODO really need to force company here? already have invoice
            # company
            force_company=company.id).new(dict(
                product_id=self.interest_product_id.id,
                quantity=1.0,
                invoice_id=invoice.id,
                partner_id=partner.id,
            ))
        line_data._onchange_product_id()

        if not line_data.account_id:
            raise UserError(_(
                'The interest product is not properly configured, '
                'missing account.'))

        line_data['price_unit'] = amount
        line_data['account_analytic_id'] = self.analytic_account_id.id
        line_data['name'] = line_data.product_id.name + '.\n' + invoice.comment

        line_values = line_data._convert_to_write(
            {field: line_data[field] for field in line_data._cache})
        return line_values
