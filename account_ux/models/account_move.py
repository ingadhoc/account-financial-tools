# flake8: noqa
import json
import base64

from odoo import models, api, fields, _, Command
from odoo.exceptions import UserError, AccessError


class AccountMove(models.Model):
    _inherit = "account.move"

    internal_notes = fields.Html()
    inverse_invoice_currency_rate = fields.Float(
        compute="_compute_inverse_invoice_currency_rate", inverse="_inverse_inverse_invoice_currency_rate"
    )

    @api.depends("invoice_currency_rate")
    def _compute_inverse_invoice_currency_rate(self):
        for rec in self:
            rec.inverse_invoice_currency_rate = 1.0 / rec.invoice_currency_rate if rec.invoice_currency_rate else 1.0

    def _inverse_inverse_invoice_currency_rate(self):
        for rec in self:
            if rec.inverse_invoice_currency_rate is not None:
                if rec.inverse_invoice_currency_rate != 0:
                    if rec.invoice_currency_rate:
                        previous_rate = 1.0 / rec.invoice_currency_rate
                        if previous_rate != rec.inverse_invoice_currency_rate:  # Verificar si realmente cambió
                            rec.message_post(
                                body=_("Invoice currency rate changed from %s to %s")
                                % (previous_rate, rec.inverse_invoice_currency_rate)
                            )
                    rec.invoice_currency_rate = 1.0 / rec.inverse_invoice_currency_rate
                else:
                    raise UserError(_("Currency rate cannot be set to zero."))

    fiscal_position_id = fields.Many2one(tracking=True)

    def get_invoice_report(self):
        self.ensure_one()
        bin_data, __ = self.env["ir.actions.report"]._render_qweb_pdf("account.account_invoices", self.id)
        pdf_base64 = base64.b64encode(bin_data).decode("ascii")
        return pdf_base64, __

    def delete_number(self):
        self.filtered(lambda x: x.state == "cancel").write({"name": "/"})

    def action_post(self):
        """After validate invoice will sent an email to the partner if the related journal has mail_template_id set"""
        # Use action_post to ensure the mail is sent only when the move is posted
        res = super().action_post()
        self.action_send_invoice_mail()
        return res

    def _post(self, soft=True):
        # Refresh the currency rate if no invoice date is set and the currency is different from company currency
        for move in self:
            if not move.invoice_date and move.currency_id != move.company_id.currency_id:
                move.refresh_invoice_currency_rate()

        return super()._post(soft=soft)

    def action_send_invoice_mail(self):
        # Backport de mejora de 19, el envío de facturas lo hacemos siempre asincrónico para no sobrecargar el proceso de posteo de factura
        for rec in self.filtered(lambda x: x.is_invoice(include_receipts=True) and x.journal_id.mail_template_id):
            if rec.partner_id.email:
                # Seteamos la data para que el cron nativo lo procese luego
                rec.sending_data = {
                    "sending_methods": ["email"],
                    "mail_template_id": rec.journal_id.mail_template_id.id,
                    "author_partner_id": self.env.user.partner_id.id,
                }
                continue
            else:
                # Si no hay email del partner, registramos un error en el chatter
                rec.message_post(
                    body=_(
                        "<b>Error enviando la factura</b>: el partner %s no tiene una dirección de correo definida.",
                        rec.partner_id.name,
                    ),
                    body_is_html=True,
                )

    def _get_mail_template(self):
        res = super()._get_mail_template()
        if self.journal_id.mail_template_id:
            res = self.journal_id.mail_template_id
        return res

    @api.onchange("partner_id")
    def _onchange_partner_commercial(self):
        if self.partner_id.user_id:
            self.invoice_user_id = self.partner_id.user_id.id

    def copy(self, default=None):
        res = super().copy(default=default)
        for line_to_clean in res.mapped("line_ids").filtered(lambda x: False in x.mapped("tax_ids.active")):
            line_to_clean.tax_ids = [
                Command.unlink(x.id) for x in line_to_clean.tax_ids.filtered(lambda x: not x.active)
            ]
        res._onchange_partner_commercial()
        return res

    # Sobrescribe el método de odoo en el PR https://github.com/odoo/odoo/pull/234605
    def get_amount_diff_foreign_currencies(self, line, move):
        def get_accounting_rate(company_currency, amount, amount_currency, currency):
            if company_currency.is_zero(amount) or currency.is_zero(amount_currency):
                return 0.0
            else:
                return abs(amount_currency) / abs(amount)

        rate = get_accounting_rate(
            move.company_id.currency_id,
            move.amount_total_signed,
            move.amount_total_in_currency_signed,
            move.currency_id,
        )
        amount = abs(line.amount_residual) * rate
        return amount

    ### Comentamos este método debido a que el campo invoice_outstanding_credits_debits_widget no se estaba seteando correctamente en super
    ### Como FIX agregamos este PR a Odoo: https://github.com/odoo/odoo/pull/234605
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

    @api.depends("invoice_date")
    def _compute_invoice_date_due(self):
        """Si la factura no tiene término de pago y la misma tiene fecha de vencimiento anterior al día de hoy y la factura no tiene fecha entonces cuando se publica la factura, la fecha de vencimiento tiene que coincidir con la fecha de hoy."""
        invoices_with_old_data_due = self.filtered(
            lambda x: (
                x.invoice_date
                and not x.invoice_payment_term_id
                and (not x.invoice_date_due or x.invoice_date_due < x.invoice_date)
            )
        )
        invoices = self - invoices_with_old_data_due
        for inv in invoices_with_old_data_due:
            if inv.invoice_date:
                inv.invoice_date_due = inv.invoice_date
        return super(AccountMove, invoices)._compute_invoice_date_due()

    @api.constrains("date", "invoice_date")
    def _check_dates_on_invoices(self):
        """Prevenir que en facturas de cliente queden distintos los campos de factura/recibo y fecha (date e invoice date). Pueden quedar distintos si se modifica alguna de esas fechas a través de edición masiva por ejemplo, entonces con esta constrains queremos prevenir que eso suceda."""
        invoices_to_check = self.filtered(
            lambda x: x.date != x.invoice_date if x.is_sale_document() and x.date and x.invoice_date else False
        )
        if invoices_to_check:
            error_msg = _("\nDate\t\t\tInvoice Date\t\tInvoice\n")
            for rec in invoices_to_check:
                error_msg += str(rec.date) + "\t" * 2 + str(rec.invoice_date) + "\t" * 3 + rec.display_name + "\n"
            raise UserError(_("The date and invoice date of a sale invoice must be the same: %s") % (error_msg))

    @api.constrains("state")
    def _check_company_on_lines(self):
        """Odoo con check company no protege bien los "tax_ids" (m2m) ni el account_id porque se computa con sql para no tener dolores de cabeza hacemos check de
        ​company al postear"""

        self.filtered(lambda x: x.state == "posted").mapped("line_ids")._check_company()

    @api.model
    def _cron_account_move_send(self, job_count=10):
        # The _render_qweb_pdf_prepare_streams method does not correctly generate individual PDF streams when the PDF outlines are missing or invalid.
        # so we set the limit into 1 in order to ensure that each PDF is generated separately.
        # mention here https://github.com/odoo/odoo/pull/230813
        # TODO v20: Check if we still need this workaround.
        job_count = 1
        super()._cron_account_move_send(job_count=job_count)

    @api.onchange("fiscal_position_id")
    def _onchange_fiscal_position_id(self):
        """
        Hacemos similar a sale_ux, cambiar FP re-computa automáticamente impuestos.
        No llamamos a action_update_fpos_values() porque hace más cosas y lo queremos matener mínimo similar a sale_ux
        """
        self.ensure_one()
        lines_to_recompute = self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
        )
        lines_to_recompute._compute_tax_ids()

    def action_open_automatic_entry_wizard(self):
        """Opens the automatic entry wizard with the invoice lines"""
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(
                _(
                    "You don't have the necessary permissions to transfer accounting entries. "
                    "Please contact your system administrator."
                )
            )

        # Support being called on multiple moves: gather lines from all selected moves
        # Filter only payable/receivable account lines
        filtered_lines = self.mapped("line_ids").filtered(
            lambda line: line.account_id.account_type in ("asset_receivable", "liability_payable")
        )

        if not filtered_lines:
            raise UserError(_("No payable/receivable lines found for the selected moves."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer Accounting Entries"),
            "res_model": "account.automatic.entry.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "account.move.line",
                "active_ids": filtered_lines.ids,
                "default_action": "change_partner",
            },
        }
