# flake8: noqa
import json
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    internal_notes = fields.Html(
        'Internal Notes'
    )
    other_currency = fields.Boolean(compute='_compute_other_currency')

    def get_invoice_report(self):
        self.ensure_one()
        bin_data, __ = self.env['ir.actions.report']._render_qweb_pdf('account.account_invoices', self.id)
        return bin_data, __

    @api.depends('company_currency_id', 'currency_id')
    def _compute_other_currency(self):
        other_currency = self.filtered(lambda x: x.company_currency_id != x.currency_id)
        other_currency.other_currency = True
        (self - other_currency).other_currency = False

    def delete_number(self):
        self.filtered(lambda x: x.state == 'cancel').write({'name': '/'})

    def _post(self, soft=True):
        move_lines = self.mapped('line_ids').filtered(
            lambda x: x.account_id.analytic_distribution_required and not x.analytic_distribution)
        if move_lines:
            raise UserError(_(
                "Some move lines don't have analytic account and "
                "analytic account is required by theese accounts.\n"
                "* Accounts: %s\n"
                "* Move lines ids: %s" % (
                    ", ".join(move_lines.mapped('account_id.name')),
                    move_lines.ids
                )
            ))
        res = super(AccountMove, self)._post(soft=soft)
        return res

    def action_post(self):
        """ After validate invoice will sent an email to the partner if the related journal has mail_template_id set """
        res = super().action_post()
        self.action_send_invoice_mail()
        return res

    def action_send_invoice_mail(self):
        for rec in self.filtered(lambda x: x.is_invoice(include_receipts=True) and x.journal_id.mail_template_id and x.partner_id.email):
            try:
                rec.message_post_with_source(
                    rec.journal_id.mail_template_id,
                    subtype_xmlid='mail.mt_comment'
                )
                rec.is_move_sent= True
            except Exception as error:
                title = _(
                    "ERROR: Invoice was not sent via email"
                )
                # message = _(
                #     "Invoice %s was correctly validate but was not send"
                #     " via email. Please review invoice chatter for more"
                #     " information" % rec.display_name
                # )
                # self.env.user.notify_warning(
                #     title=title,
                #     message=message,
                #     sticky=True,
                # )
                rec.message_post(body="<br/><br/>".join([
                    "<b>" + title + "</b>",
                    _("Please check the email template associated with"
                      " the invoice journal."),
                    "<code>" + str(error) + "</code>"
                ]), body_is_html=True
                )

    @api.onchange('partner_id')
    def _onchange_partner_commercial(self):
        if self.partner_id.user_id:
            self.invoice_user_id = self.partner_id.user_id.id

    def copy(self, default=None):
        res = super().copy(default=default)
        res._onchange_partner_commercial()
        return res

    # Sobrescribe el método de odoo en el PR https://github.com/odoo/odoo/pull/170066/files
    def get_amount_diff_foreign_currencies(self, line, move):
        def get_accounting_rate(company_currency, amount, amount_currency, currency):
            if company_currency.is_zero(amount) or currency.is_zero(amount_currency):
                return 0.0
            else:
                return abs(amount_currency) / abs(amount)

        rate = get_accounting_rate(move.company_id.currency_id, move.amount_total_signed, move.amount_total_in_currency_signed, move.currency_id)
        amount = abs(line.amount_residual) * rate 
        return amount

    ### Comentamos este método debido a que el campo invoice_outstanding_credits_debits_widget no se estaba seteando correctamente en super
    ### Como FIX agregamos este PR a Odoo: https://github.com/odoo/odoo/pull/170066/files

    # def _compute_payments_widget_to_reconcile_info(self):
    #     """
    #     Modificamos el widget para que si la compañía tiene el setting de forzar concilacion en moneda y estamos
    #     en esa situacion (cuenta deudora no tiene moneda). Entonces el importe que previsualizamos para conciliar
    #     respeta la modificacion que hacemos al conciliar (basicamente que importa el rate en pesos por lo cual tomamos
    #     el rate de la factura)
    #     """
    #     super()._compute_payments_widget_to_reconcile_info()

    #     def get_accounting_rate(company_currency, amount, amount_currency, currency):
    #         if company_currency.is_zero(amount) or currency.is_zero(amount_currency):
    #             return 0.0
    #         else:
    #             return abs(amount_currency) / abs(amount)

    #     # TODO tal vez chequear tmb que moneda de factura sea distinta? o eso no influye? habria que ver caso de pagar con usd factura en ars
    #     for move in self.filtered(
    #             lambda x: x.invoice_has_outstanding and \
    #             x.company_id.currency_id != x.currency_id and x.company_id.reconcile_on_company_currency):
    #         pay_term_lines = move.line_ids\
    #             .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
    #         # deberia ser solo una cuenta, pero como super hace un in chequeamos que cualquier cuenta pueda tener moneda
    #         if any(x.currency_id for x in pay_term_lines.account_id):
    #             continue
    #         # para todos los asientos que son en moneda secundaria y que no tengan moneda calculamos el rate
    #         # segun lo contable y previsualizamos la imputacion con este rate

    #         # los rates en realidad existen en los aml de la factura, pero para no tomar arbitrariamente uno sacamos
    #         # el rate desde los totales de la factura
    #         rate = get_accounting_rate(move.company_id.currency_id, move.amount_total_signed, move.amount_total_in_currency_signed, move.currency_id)
    #         for item in move.invoice_outstanding_credits_debits_widget['content']:
    #             amount_residual = self.env['account.move.line'].browse(item['id']).amount_residual
    #             item['amount'] = move.currency_id.round(amount_residual * rate)

    @api.depends('invoice_date')
    def _compute_invoice_date_due(self):
        """ Si la factura no tiene término de pago y la misma tiene fecha de vencimiento anterior al día de hoy y la factura no tiene fecha entonces cuando se publica la factura, la fecha de vencimiento tiene que coincidir con la fecha de hoy. """
        invoices_with_old_data_due = self.filtered(lambda x: x.invoice_date and not x.invoice_payment_term_id and (not x.invoice_date_due or x.invoice_date_due < x.invoice_date))
        invoices = self - invoices_with_old_data_due
        for inv in invoices_with_old_data_due:
            if inv.invoice_date:
                inv.invoice_date_due = inv.invoice_date
        return super(AccountMove, invoices)._compute_invoice_date_due()

    @api.constrains('date', 'invoice_date')
    def _check_dates_on_invoices(self):
        """ Prevenir que en facturas de cliente queden distintos los campos de factura/recibo y fecha (date e invoice date). Pueden quedar distintos si se modifica alguna de esas fechas a través de edición masiva por ejemplo, entonces con esta constrains queremos prevenir que eso suceda.  """
        invoices_to_check = self.filtered(lambda x: x.date!=x.invoice_date if x.is_sale_document() and x.date and x.invoice_date else False)
        if invoices_to_check:
            error_msg = _('\nDate\t\t\tInvoice Date\t\tInvoice\n')
            for rec in invoices_to_check:
                error_msg +=  str(rec.date) + '\t'*2 + str(rec.invoice_date) + '\t'*3 + rec.display_name + '\n'
            raise UserError(_('The date and invoice date of a sale invoice must be the same: %s') % (error_msg))
