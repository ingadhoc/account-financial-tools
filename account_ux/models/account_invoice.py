##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    # this field should be named amount_untaxed_signed and the odoo
    # amount_untaxed_signed should be named amount_untaxed_company_signed
    amount_untaxed_signed_real = fields.Monetary(
        string="Untaxed Amount",
        store=True,
        readonly=True,
        compute='_compute_amount'
    )

    @api.depends(
        'invoice_line_ids.price_subtotal', 'tax_line_ids.amount',
        'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        # because super method is api.one
        for rec in self:
            super(AccountInvoice, rec)._compute_amount()
            sign = rec.type in ['in_refund', 'out_refund'] and -1 or 1
            rec.amount_untaxed_signed_real = rec.amount_untaxed * sign

    @api.multi
    def invoice_cancel_from_done(self):
        for rec in self:
            if not rec.payment_move_line_ids and rec.state == 'paid':
                rec.action_cancel()

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
                rec.message_post("<br/><br/>".join([
                    "<b>" + title + "</b>",
                    _("Please check the email template associated with"
                      " the invoice journal."),
                    "<code>" + str(error) + "</code>"
                ]),
                )
        return res

    @api.multi
    def action_invoice_draft(self):
        invoice_data = [(x, x.date) for x in self.filtered('date')]
        res = super(AccountInvoice, self).action_invoice_draft()
        for rec, date in invoice_data:
            rec.date = date
        return res
