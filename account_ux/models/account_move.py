# flake8: noqa
import json
import base64
from odoo import models, api, fields, _, Command
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    internal_notes = fields.Html()
    inverse_invoice_currency_rate = fields.Float(compute="_compute_inverse_invoice_currency_rate")

    def get_invoice_report(self):
        self.ensure_one()
        bin_data, __ = self.env["ir.actions.report"]._render_qweb_pdf("account.account_invoices", self.id)
        pdf_base64 = base64.b64encode(bin_data).decode("ascii")
        return pdf_base64, __

    def delete_number(self):
        self.filtered(lambda x: x.state == "cancel").write({"name": "/"})

    def _post(self, soft=True):
        """After validate invoice will sent an email to the partner if the related journal has mail_template_id set"""
        res = super()._post(soft=soft)
        self.action_send_invoice_mail()
        return res

    def action_send_invoice_mail(self):
        for rec in self.filtered(lambda x: x.is_invoice(include_receipts=True) and x.journal_id.mail_template_id):
            if rec.partner_id.email:
                try:
                    rec.message_post_with_source(rec.journal_id.mail_template_id, subtype_xmlid="mail.mt_comment")
                    rec.is_move_sent = True
                except Exception as error:
                    title = _("ERROR: Invoice was not sent via email")
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
                    rec.message_post(
                        body="<br/><br/>".join(
                            [
                                "<b>" + title + "</b>",
                                _("Please check the email template associated with the invoice journal."),
                                "<code>" + str(error) + "</code>",
                            ]
                        ),
                        body_is_html=True,
                    )
            else:
                rec.message_post(
                    body=_(
                        "<b>Error sending the invoice</b>: partner %s does not have an email address defined.",
                        rec.partner_id.name,
                    ),
                    body_is_html=True,
                )

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

    # Sobrescribe el método de odoo en el PR https://github.com/odoo/odoo/pull/170066/files
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
    ### Como FIX agregamos este PR a Odoo: https://github.com/odoo/odoo/pull/184611

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
            lambda x: x.invoice_date
            and not x.invoice_payment_term_id
            and (not x.invoice_date_due or x.invoice_date_due < x.invoice_date)
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

    @api.depends("invoice_currency_rate")
    def _compute_inverse_invoice_currency_rate(self):
        for record in self:
            record.inverse_invoice_currency_rate = (
                1 / record.invoice_currency_rate if record.invoice_currency_rate else 1.0
            )

    @api.constrains("state")
    def _check_company_on_lines(self):
        """Odoo con check company no protege bien los "tax_ids" (m2m) ni el account_id porque se computa con sql para no tener dolores de cabeza hacemos check de
        ​company al postear"""

        self.filtered(lambda x: x.state == "posted").mapped("line_ids")._check_company()

    @api.depends()
    def _compute_tax_totals(self):
        super()._compute_tax_totals()

        for move in self.filtered(lambda x: x.state == "posted"):
            base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()

            # Detectar si hay impuestos inactivos en las líneas de impuestos
            inactive_trl_ids = {
                t["tax_repartition_line_id"].id
                for t in _tax_lines
                if t["tax_repartition_line_id"] and not t["tax_repartition_line_id"].tax_id.active
            }
            if not inactive_trl_ids:
                continue

            move.tax_totals = self._replace_inactive_tax_amounts(move, _tax_lines, inactive_trl_ids)

    def _replace_inactive_tax_amounts(self, move, _tax_lines, inactive_trl_ids):
        tax_totals = move.tax_totals
        subtotal = tax_totals["subtotals"][0]
        tax_groups = subtotal["tax_groups"]

        # 1. Acumular valores por tax_group
        amounts_by_group = {}

        for t in _tax_lines:
            trl = t["tax_repartition_line_id"]
            if not trl or trl.id not in inactive_trl_ids:
                continue

            group_id = trl.tax_id.tax_group_id.id
            vals = amounts_by_group.setdefault(group_id, {"amount_currency": 0.0, "amount": 0.0})

            vals["amount_currency"] += t["amount_currency"]
            vals["amount"] += t["balance"]

        if not amounts_by_group:
            return tax_totals

        # 2.Reemplazar valores en los tax_groups
        for g in tax_groups:
            group_id = g["id"]
            if group_id in amounts_by_group:
                vals = amounts_by_group[group_id]
                g["tax_amount_currency"] = abs(vals["amount_currency"])
                g["tax_amount"] = abs(vals["amount"])

        # 3. Recalcular subtotales
        subtotal["tax_amount_currency"] = sum(g["tax_amount_currency"] for g in tax_groups)
        subtotal["tax_amount"] = sum(g["tax_amount"] for g in tax_groups)

        # 4. Recalcular totales principales
        tax_totals["tax_amount_currency"] = subtotal["tax_amount_currency"]
        tax_totals["tax_amount"] = subtotal["tax_amount"]
        tax_totals["total_amount_currency"] = tax_totals["base_amount_currency"] + subtotal["tax_amount_currency"]
        tax_totals["total_amount"] = tax_totals["base_amount"] + subtotal["tax_amount"]

        return tax_totals

    def button_draft(self):
        for move in self:
            if move.inalterable_hash and not move.journal_id.restrict_mode_hash_table:
                move.env.cr.execute("update account_move set inalterable_hash = null where id = %s", (move.id,))
                move.invalidate_recordset(["inalterable_hash"])
        return super().button_draft()
