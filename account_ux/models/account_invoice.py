##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.onchange('partner_id')
    def _onchange_partner_commercial(self):
        if self.partner_id.user_id:
            self.user_id = self.partner_id.user_id.id

    @api.multi
    def action_invoice_open(self):
        """ After validate invoice will sent an email to the partner if the
        related journal has mail_template_id set.
        """
        for rec in self:
            line_taxes = rec.invoice_line_ids.mapped('invoice_line_tax_ids')
            invoice_taxes = rec.tax_line_ids.filtered(
                lambda x: not x.manual).mapped('tax_id')
            wrong_taxes = set(line_taxes) - set(invoice_taxes)
            if wrong_taxes:
                raise UserError(_(
                    'Los impuestos "%s" están definidos en líneas '
                    'de factura pero no están presentes en los impuestos de '
                    'factura, es probable que los haya borrado sin querer. '
                    'Por favor, recalcule los impuestos modificando alguna '
                    'línea de la factura. ') % (
                        ', '.join([x.name for x in wrong_taxes])))
        res = super(AccountInvoice, self). action_invoice_open()
        for rec in self.filtered('journal_id.mail_template_id'):
            try:
                rec.message_post_with_template(
                    rec.journal_id.mail_template_id.id,
                )
            except Exception as error:
                title = _(
                    "ERROR: Invoice was not sent via email"
                )
                message = _(
                    "Invoice %s was correctly validate but was not send"
                    " via email. Please review invoice chatter for more"
                    " information" % rec.display_name
                )
                self.env.user.notify_warning(
                    title=title,
                    message=message,
                    sticky=True,
                )
                rec.message_post(body="<br/><br/>".join([
                    "<b>" + title + "</b>",
                    _("Please check the email template associated with"
                      " the invoice journal."),
                    "<code>" + str(error) + "</code>"
                ]),
                )
        return res

    @api.multi
    def action_invoice_draft(self):
        """ This is for supplier invoices where, if you force an accounting
        date and if you need to cancel the invoice to fix something on the
        invoice, you don't want the accounting date to get lost.
        We only keep the accounting date if it was forced (different to the
        invoice date)
        """
        invoice_data = [(x, x.date) for x in self.filtered(
            lambda x: x.type in ['in_invoice', 'in_refund'] and
            x.date != x.date_invoice)]
        res = super(AccountInvoice, self).action_invoice_draft()
        for rec, date in invoice_data:
            rec.date = date
        return res

    @api.onchange('date_invoice')
    def onchange_invoice_date(self):
        if self.date:
            return {'warning': {
                'title': _("Warning!"),
                'message': _(
                    'You are changing the Invoice Date but you have force an '
                    'accounting date.\n Please check if you need to update '
                    'the accounting date too.')}}

    @api.multi
    def copy(self, default=None):
        res = super(AccountInvoice, self).copy(default=default)
        res._onchange_partner_commercial()
        return res

    # TODO parece no ser necesario, ver si borramos en v13 o mas adelante en
    # v12
    # # TODO borrar porque al fianl estamos desactivando cambio de moneda
    # # sin importar si viene o no la clave en el contexto
    # # We do this for a bug when creating an invoice from
    # # the PO that does not get the correct currency from the PO, by default
    # # bring the currency of the newspaper.
    # # we also add this so that in a multic environment if you change company
    # # currency is not changed
    # @api.onchange('journal_id')
    # def _onchange_journal_id(self):
    #     """
    #     desactivamos cambio de moneda ya que el cambio de moneda no actualiza
    #     precios y en realidad en la mayoria de los casos no quermeos que
    #     cambiar diario cambie moneda.
    #     """
    #     currency = self.currency_id
    #     super(AccountInvoice, self)._onchange_journal_id()
    #     self.currency_id = currency
    #     # if self._context.get('default_currency_id', False):
    #     #     self.currency_id = self._context.get('default_currency_id')
    #     # else:
    #     #     super(AccountInvoice, self)._onchange_journal_id()

    @api.multi
    def compute_taxes(self):
        _logger.info('Checking compute taxes on draft invoices')
        if not self._context.get('force_compute_taxes') and self.filtered(
                lambda x: x.state != 'draft'):
            raise UserError(_(
                'You can compute taxes invoices that are not in draft only if '
                'you send "force_compute_taxes=True" on context. Be aware'
                'invoices amounts could change'))
        return super().compute_taxes()

    @api.multi
    def assign_outstanding_credit(self, credit_aml_id):
        """ aplicación de este parche
        https://github.com/odoo/odoo/pull/25485/files
        """
        self.ensure_one()
        credit_aml = self.env['account.move.line'].browse(credit_aml_id)
        if credit_aml.payment_id:
            credit_aml.payment_id.write({'invoice_ids': [(4, self.id, None)]})
        return self.register_payment(credit_aml)
