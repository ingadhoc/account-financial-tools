from odoo import fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_payment_term_surcharges(self):
        result = []
        for surcharge in self.invoice_payment_term_id.surcharge_ids:
            result.append({'date': surcharge._calculate_date(self.invoice_date), 'surcharge': surcharge.surcharge})
        result.sort(key=lambda x: x['date'])
        return result

    def _cron_recurring_surcharges_invoices(self):
        _logger.info('Running Surcharges Invoices Cron Job')
        self.search([
            ('invoice_payment_term_id.surcharge_ids', '!=', False),
            ('state', '=', 'posted'),
            ('payment_state', '=', 'not_paid')],
            # buscamos facturas que tengan surcharges, esten posteadas y aun no pagadas
            ).create_surcharges_invoices()

    def create_surcharges_invoices(self):
        for rec in self:
            _logger.info(
                'Creating Surcharges Invoices (id: %s, company: %s)', rec.id,
                rec.company_id.name)
            current_date = fields.Date.context_today(self)
            surcharges = rec._get_payment_term_surcharges()
            for surcharge in surcharges:
                if surcharge.get('date') <= current_date and surcharge.get('date') not in rec.debit_note_ids.mapped('invoice_date'):
                    # si tiene un surcharge el dia de hoy, se evalua que no tenga notas de debito
                    # con fecha de hoy, en caso de que tenga, se corre el create_invoice
                    rec.create_surcharge_invoice(surcharge)

    def create_surcharge_invoice(self, surcharge):
        self.ensure_one()
        product = self.company_id.payment_term_surcharge_product_id
        if not product:
            raise UserError('Atención, debes configurar un producto por defecto para que aplique a la hora de crear las facturas de recargo')
        debt = self.amount_residual
        surcharge_percent = surcharge.get('surcharge')
        to_date = surcharge.get('date')
        move_debit_note_wiz = self.env['account.debit.note'].with_context(active_model="account.move",
                                                                          active_ids=self.ids).create({
            'date': to_date,
            'reason': 'Surcharge Invoice',
        })
        debit_note = self.env['account.move'].browse(move_debit_note_wiz.create_debit().get('res_id'))
        debit_note.narration = product.name + '.\n' + self.prepare_info(to_date, debt, surcharge.get('surcharge'))
        debit_note.write({'invoice_line_ids': self._prepare_surcharge_line(product, debt, to_date, surcharge_percent)})
        if self.company_id.payment_term_surcharge_invoice_auto_post:
            try:
                debit_note.action_post()
            except Exception as exp:
                _logger.error(
                    "Something went wrong validating "
                    "surcharge invoice: {}".format(exp))
                raise exp

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

    def _prepare_surcharge_line(self, product, debt, to_date, surcharge):
        self.ensure_one()
        partner = self.partner_id
        comment = self.prepare_info(to_date, debt, surcharge)
        # fpos = partner.property_account_position_id
        # taxes = product.taxes_id.filtered(
        #     lambda r: r.company_id == self.company_id)
        # tax_id = fpos.map_tax(taxes, product)
        #TODO ver si se agrega el tax manualmente o no
        invoice_line_vals = [(0, 0, {
                "product_id": product.id,
                "quantity": 1.0,
                "price_unit": (surcharge / 100) * debt,
                "partner_id": partner.id,
                "name": product.name + '.\n' + comment,
                # "analytic_account_id": self.env.context.get('analytic_id', False),
                # "tax_ids": [(6, 0, tax_id.ids)]
            })]

        return invoice_line_vals
