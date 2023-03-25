# flake8: noqa
import json
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    internal_notes = fields.Html(
        'Internal Notes'
    )
    reversed_entry_id = fields.Many2one(
        'account.move',
        states={'draft': [('readonly', False)]},
    )
    other_currency = fields.Boolean(compute='_compute_other_currency')

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
        for rec in self.filtered(lambda x: x.is_invoice(include_receipts=True) and x.journal_id.mail_template_id):
            try:
                rec.message_post_with_template(
                    rec.journal_id.mail_template_id.id,
                )
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
                ]),
                )

    @api.onchange('partner_id')
    def _onchange_partner_commercial(self):
        if self.partner_id.user_id:
            self.invoice_user_id = self.partner_id.user_id.id

    def copy(self, default=None):
        res = super().copy(default=default)
        res._onchange_partner_commercial()
        return res

    def _compute_payments_widget_to_reconcile_info(self):
        """
        Modificamos el widget para que si la compañía tiene el setting de forzar concilacion en moneda y estamos
        en esa situacion (cuenta deudora no tiene moneda). Entonces el importe que previsualizamos para conciliar
        respeta la modificacion que hacemos al conciliar (basicamente que importa el rate en pesos por lo cual tomamos
        el rate de la factura)
        """
        super()._compute_payments_widget_to_reconcile_info()

        def get_accounting_rate(company_currency, amount, amount_currency, currency):
            if company_currency.is_zero(amount) or currency.is_zero(amount_currency):
                return 0.0
            else:
                return abs(amount_currency) / abs(amount)

        # TODO tal vez chequear tmb que moneda de factura sea distinta? o eso no influye? habria que ver caso de pagar con usd factura en ars
        for move in self.filtered(
                lambda x: x.invoice_outstanding_credits_debits_widget and \
                x.company_id.currency_id != x.currency_id and x.company_id.reconcile_on_company_currency):
            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
            # deberia ser solo una cuenta, pero como super hace un in chequeamos que cualquier cuenta pueda tener moneda
            if any(x.currency_id for x in pay_term_lines.account_id):
                continue
            # para todos los asientos que son en moneda secundaria y que no tengan moneda calculamos el rate
            # segun lo contable y previsualizamos la imputacion con este rate

            # los rates en realidad existen en los aml de la factura, pero para no tomar arbitrariamente uno sacamos
            # el rate desde los totales de la factura
            rate = get_accounting_rate(move.company_id.currency_id, move.amount_total_signed, move.amount_total_in_currency_signed, move.currency_id)
            for item in move.invoice_outstanding_credits_debits_widget['content']:
                amount_residual = self.env['account.move.line'].browse(item['id']).amount_residual
                item['amount'] = move.currency_id.round(amount_residual * rate)
