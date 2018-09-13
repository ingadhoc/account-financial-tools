# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
import json
from openerp import models, api, _
from openerp.exceptions import ValidationError
from openerp.tools import float_is_zero
import logging


_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None,
               date=None, description=None, journal_id=None):
        """
        En las facturas rectificativas no se calculan bien los impuestos (por)
        ej. el campo base. Esto arregla eso
        """
        new_invoices = super(AccountInvoice, self).refund(
            date_invoice=date_invoice, date=date,
            description=description, journal_id=journal_id)
        new_invoices.write({'date_due': False})
        new_invoices.compute_taxes()
        return new_invoices

    # TODO borrar porque al fianl estamos desactivando cambio de moneda
    # sin importar si viene o no la clave en el contexto
    # We do this for a bug when creating an invoice from
    # the PO that does not get the correct currency from the PO, by default
    # bring the currency of the newspaper.
    # we also add this so that in a multic environment if you change company
    # currency is not changed
    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        """
        desactivamos cambio de moneda ya que el cambio de moneda no actualiza
        precios y en realidad en la mayoria de los csaos no quermeos que
        cambiar diario cambie moneda.
        """
        currency = self.currency_id
        super(AccountInvoice, self)._onchange_journal_id()
        self.currency_id = currency
        # if self._context.get('default_currency_id', False):
        #     self.currency_id = self._context.get('default_currency_id')
        # else:
        #     super(AccountInvoice, self)._onchange_journal_id()

    @api.multi
    def compute_taxes(self):
        _logger.info('Checking compute taxes on draft invoices')
        if not self._context.get('force_compute_taxes') and self.filtered(
                lambda x: x.state != 'draft'):
            raise ValidationError(_(
                'You can compute taxes invoices that are not in draft only if '
                'you send "force_compute_taxes=True" on context. Be aware'
                'invoices amounts could change'))
        return super(AccountInvoice, self).compute_taxes()

    @api.one
    @api.depends('payment_move_line_ids.amount_residual')
    def _get_payment_info_JSON(self):
        """Backport of fix on v11 using invoice date for currency rate
        fix between start fix / end fix comments
        """
        self.payments_widget = json.dumps(False)
        if self.payment_move_line_ids:
            info = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            currency_id = self.currency_id
            for payment in self.payment_move_line_ids:
                payment_currency_id = False
                if self.type in ('out_invoice', 'in_refund'):
                    amount = sum([p.amount for p in payment.matched_debit_ids if p.debit_move_id in self.move_id.line_ids])
                    amount_currency = sum([p.amount_currency for p in payment.matched_debit_ids if p.debit_move_id in self.move_id.line_ids])
                    if payment.matched_debit_ids:
                        payment_currency_id = all([p.currency_id == payment.matched_debit_ids[0].currency_id for p in payment.matched_debit_ids]) and payment.matched_debit_ids[0].currency_id or False
                elif self.type in ('in_invoice', 'out_refund'):
                    amount = sum([p.amount for p in payment.matched_credit_ids if p.credit_move_id in self.move_id.line_ids])
                    amount_currency = sum([p.amount_currency for p in payment.matched_credit_ids if p.credit_move_id in self.move_id.line_ids])
                    if payment.matched_credit_ids:
                        payment_currency_id = all([p.currency_id == payment.matched_credit_ids[0].currency_id for p in payment.matched_credit_ids]) and payment.matched_credit_ids[0].currency_id or False
                # get the payment value in invoice currency
                if payment_currency_id and payment_currency_id == self.currency_id:
                    amount_to_show = amount_currency
                else:
                    # start fix
                    amount_to_show = payment.company_id.currency_id.with_context(date=self.date).compute(amount, self.currency_id)
                    # end fix
                if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                    continue
                payment_ref = payment.move_id.name
                if payment.move_id.ref:
                    payment_ref += ' (' + payment.move_id.ref + ')'
                info['content'].append({
                    'name': payment.name,
                    'journal_name': payment.journal_id.name,
                    'amount': amount_to_show,
                    'currency': currency_id.symbol,
                    'digits': [69, currency_id.decimal_places],
                    'position': currency_id.position,
                    'date': payment.date,
                    'payment_id': payment.id,
                    'move_id': payment.move_id.id,
                    'ref': payment_ref,
                })
            self.payments_widget = json.dumps(info)
