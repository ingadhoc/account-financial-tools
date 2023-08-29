from odoo import fields, models, _, api
from odoo.exceptions import UserError
from odoo.tools import float_round

import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    next_surcharge_date = fields.Date(compute='_compute_next_surcharge', store=True)
    next_surcharge_percent = fields.Float(compute='_compute_next_surcharge', store=True)

    def _cron_recurring_surcharges_invoices(self, batch_size=60):
        current_date = fields.Date.context_today(self)
        domain = [
            ('next_surcharge_date', '<=', current_date),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'not_paid')]
        _logger.info('Running Surcharges Invoices Cron Job, pendientes por procesar %s facturas' % self.search_count(domain))
        to_create = self.search(domain)
        to_create[:batch_size].create_surcharges_invoices()
        if len(to_create) > batch_size:
            self.env.ref('account_payment_term_surcharge.cron_recurring_surcharges_invoices')._trigger()

    def create_surcharges_invoices(self):
        for rec in self:
            _logger.info(
                'Creating Surcharges Invoices (id: %s, company: %s)', rec.id,
                rec.company_id.name)
            rec.create_surcharge_invoice(rec.next_surcharge_date, rec.next_surcharge_percent)

    def create_surcharge_invoice(self, surcharge_date, surcharge_percent):
        self.ensure_one()
        product = self.company_id.payment_term_surcharge_product_id
        if not product:
            raise UserError('Atención, debes configurar un producto por defecto para que aplique a la hora de crear las facturas de recargo')
        debt = self.amount_residual
        move_debit_note_wiz = self.env['account.debit.note'].with_context(active_model="account.move",
                                                                          active_ids=self.ids).create({
            'date': surcharge_date,
            'reason': 'Surcharge Invoice',
        })
        debit_note = self.env['account.move'].browse(move_debit_note_wiz.create_debit().get('res_id'))
        debit_note.narration = product.name + '.\n' + self.prepare_info(surcharge_date, debt, surcharge_percent)
        self._add_surcharge_line(debit_note, product, debt, surcharge_date, surcharge_percent)
        if self.company_id.payment_term_surcharge_invoice_auto_post:
            try:
                debit_note.action_post()
            except Exception as exp:
                _logger.error(
                    "Something went wrong validating "
                    "surcharge invoice: {}".format(exp))
                raise exp
        self._compute_next_surcharge()

    def prepare_info(self, to_date, debt, surcharge):
        self.ensure_one()
        # Format date to customer language
        lang_code = self.env.context.get('lang', self.env.user.lang)
        lang = self.env['res.lang']._lang_get(lang_code)
        date_format = lang.date_format
        to_date_format = to_date.strftime(date_format)
        res = _(
            'Deuda Vencida al %s: %s\n'
            'Tasa de interés: %s') % (
                to_date_format, debt, surcharge)
        return res

    def _add_surcharge_line(self, debit_note, product, debt, to_date, surcharge):
        self.ensure_one()
        # partner = self.partner_id
        comment = self.prepare_info(to_date, debt, surcharge)
        debit_note.write({'invoice_line_ids': [(0, 0, {
            "product_id": product.id,
        })]})
        debit_note = debit_note.with_context(check_move_validity=False)
        debit_note.invoice_line_ids._onchange_product_id()
        debit_note.invoice_line_ids[0].price_unit = float_round((surcharge / 100) * debt, precision_digits=2)
        debit_note.invoice_line_ids[0].name = product.name + '.\n' + comment
        debit_note._recompute_dynamic_lines()

    @api.depends('invoice_payment_term_id', 'invoice_date')
    def _compute_next_surcharge(self):
        for rec in self:
            if rec.invoice_payment_term_id.surcharge_ids != False:
                surcharges = []
                debit_note_dates = rec.debit_note_ids.mapped('invoice_date')
                for surcharge in rec.invoice_payment_term_id.surcharge_ids:
                    tentative_date = surcharge._calculate_date(rec.invoice_date)
                    if tentative_date not in debit_note_dates:
                        surcharges.append({'date': tentative_date, 'surcharge': surcharge.surcharge})
                surcharges.sort(key=lambda x: x['date'])
                if len(surcharges) > 0:
                    rec.next_surcharge_date = surcharges[0].get('date')
                    rec.next_surcharge_percent = surcharges[0].get('surcharge')
                else:
                    rec.next_surcharge_date = False
                    rec.next_surcharge_percent = False
            else:
                rec.next_surcharge_date = False
                rec.next_surcharge_percent = False
