##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None,
               date=None, description=None, journal_id=None):
        """
        En las facturas rectificativas no se calculan bien los impuestos (por
        ej. el campo base). Esto arregla eso y además blanquea la fecha
        de vencimiento que por defecto es duplicada desde la factura original
        y nos puede traer errores en factura electronica
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
        precios y en realidad en la mayoria de los casos no quermeos que
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
