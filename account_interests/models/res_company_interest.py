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
    tolerance_interval = fields.Integer(
        'Tolerance',
        default=1,
        help="Number of periods of tolerance for dues. 0 = no tolerance"
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
            interests_date = rec.next_date

            rule_type = rec.rule_type
            interval = rec.interval
            tolerance_interval = rec.tolerance_interval

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

            # buscamos solo facturas que vencieron
            # antes de hoy menos un periodo
            # TODO ver si queremos que tambien se calcule interes proporcional
            # para lo que vencio en este ultimo periodo
            to_date = interests_date - tolerance_delta
            from_date = to_date - tolerance_delta
            # llamamos a crear las facturas con la compañia del interes para
            # que tome correctamente las cuentas
            rec.with_company(rec.company_id).with_context(default_l10n_ar_afip_asoc_period_start=from_date,
                             default_l10n_ar_afip_asoc_period_end=to_date).create_invoices(to_date)

            # seteamos proxima corrida en hoy mas un periodo
            rec.next_date = interests_date + next_delta

    def _get_move_line_domains(self, to_date):
        self.ensure_one()
        move_line_domain = [
            ('account_id', 'in', self.receivable_account_ids.ids),
            ('full_reconcile_id', '=', False),
            ('date_maturity', '<', to_date),
            ('partner_id.active', '=', True),
            ('parent_state', '=', 'posted'),
        ]
        return move_line_domain

    def create_invoices(self, to_date, groupby=['partner_id']):
        self.ensure_one()

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)], limit=1)
        
        if self.receivable_account_ids != journal.default_account_id:
            journal = self.env['account.journal'].search([('default_account_id','in',self.receivable_account_ids.ids)], limit=1) or journal

        move_line_domain = self._get_move_line_domains(to_date)
        # Check if a filter is set
        if self.domain:
            move_line_domain += safe_eval(self.domain)

        fields = ['id:recordset', 'amount_residual:sum', 'partner_id:recordset', 'account_id:recordset']

        move_line = self.env['account.move.line']
        grouped_lines = move_line._read_group(
            domain=move_line_domain,
            groupby=groupby,
            aggregates=fields,
        )
        self = self.with_context(
            company_id=self.company_id.id,
            mail_notrack=True,
            prefetch_fields=False).with_company(self.company_id)

        total_items = len(grouped_lines)
        _logger.info('%s interest invoices will be generated', total_items)
        for idx, line in enumerate(grouped_lines):
            move_vals = self._prepare_interest_invoice(
                line, to_date, journal)

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

    def _prepare_interest_invoice(self, line, to_date, journal):
        self.ensure_one()
        debt = line[2]

        if not debt or debt <= 0.0:
            _logger.info("Debt is negative, skipping...")
            return

        partner_id = line[0].id
        partner = self.env['res.partner'].browse(partner_id)
        comment = self.prepare_info(to_date, debt)
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
            'invoice_payment_term_id': False,
            'narration': self.interest_product_id.name + '.\n' + comment,
            'invoice_line_ids': [(0, 0, {
                "product_id": self.interest_product_id.id,
                "quantity": 1.0,
                "price_unit": self.rate * debt,
                "partner_id": partner.id,
                "name": self.interest_product_id.name + '.\n' + comment,
                "analytic_distribution": {self.analytic_account_id.id: 100.0} if self.analytic_account_id.id else False,
                "tax_ids": [(6, 0, tax_id.ids)]
            })],
        }

        # hack para evitar modulo glue con l10n_latam_document
        # hasta el momento tenemos feedback de dos clientes uruguayos de que los ajustes por intereses 
        # se hacen comoo factura normal y no ND. Si eventualmente otros clintes solicitan ND tendremos 
        # que analizar hacerlo parametrizable y además cambios en validación electrónica con DGI 
        # porque actualmente exige vincular una factura original (implementar poder pasar indicadores globales)
        if journal.country_code != 'UY' and journal._fields.get('l10n_latam_use_documents') and journal.l10n_latam_use_documents:
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
