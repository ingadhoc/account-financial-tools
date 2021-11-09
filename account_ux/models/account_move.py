# flake8: noqa
import json
from odoo.tools import float_is_zero
from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    internal_notes = fields.Text(
        'Internal Notes'
    )
    reversed_entry_id = fields.Many2one(
        'account.move',
        states={'draft': [('readonly', False)]},
    )

    def delete_number(self):
        self.filtered(lambda x: x.state == 'cancel').write({'name': '/'})

    def post(self):
        move_lines = self.mapped('line_ids').filtered(
            lambda x: (
                x.account_id.user_type_id.analytic_tag_required and
                x.account_id.analytic_tag_required != 'optional' or
                x.account_id.analytic_tag_required == 'required')
            and not x.analytic_tag_ids)
        if move_lines:
            raise UserError(_(
                "Some move lines don't have analytic tags and "
                "analytic tags are required by theese accounts.\n"
                "* Accounts: %s\n"
                "* Move lines ids: %s" % (
                    ", ".join(move_lines.mapped('account_id.name')),
                    move_lines.ids
                )
            ))

        move_lines = self.mapped('line_ids').filtered(
            lambda x: (
                x.account_id.user_type_id.analytic_account_required and
                x.account_id.analytic_account_required != 'optional' or
                x.account_id.analytic_account_required == 'required')
            and not x.analytic_account_id)
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
        res = super(AccountMove, self).post()
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
        for move in self:
            move.invoice_outstanding_credits_debits_widget = json.dumps(False)
            move.invoice_has_outstanding = False

            if move.state != 'posted' or move.invoice_payment_state != 'not_paid' or not move.is_invoice(include_receipts=True):
                continue
            pay_term_line_ids = move.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))

            domain = [('account_id', 'in', pay_term_line_ids.mapped('account_id').ids),
                      '|', ('move_id.state', '=', 'posted'), '&', ('move_id.state', '=', 'draft'), ('journal_id.post_at', '=', 'bank_rec'),
                      ('partner_id', '=', move.commercial_partner_id.id),
                      ('reconciled', '=', False), '|', ('amount_residual', '!=', 0.0),
                      ('amount_residual_currency', '!=', 0.0)]

            if move.is_inbound():
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'move_id': move.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = move.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == move.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        currency = line.company_id.currency_id
                        # as we dont add the currency information we use the rate of the invoice that is the one used by odoo compute amount_residual
                        # INICIO CAMBIO
                        if move.company_id.country_id == self.env.ref('base.ar'):
                            amount_to_show = currency._convert(abs(line.amount_residual), move.currency_id, move.company_id,
                                                            move.invoice_date or fields.Date.today())
                        else:
                            amount_to_show = currency._convert(abs(line.amount_residual), move.currency_id, move.company_id,
                                                            line.date or fields.Date.today())
                        # FIN CAMBIO
                    if float_is_zero(amount_to_show, precision_rounding=move.currency_id.rounding):
                        continue
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, move.currency_id.decimal_places],
                        'payment_date': fields.Date.to_string(line.date),
                    })
                info['title'] = type_payment
                move.invoice_outstanding_credits_debits_widget = json.dumps(info)
                move.invoice_has_outstanding = True

    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            # In case we are in an onchange, line_ids is a NewId, not an integer. By using line_ids.ids we get the correct integer value.
            counterpart_line = counterpart_lines.filtered(lambda line: line.id not in self.line_ids.ids)

            if foreign_currency and partial.currency_id == foreign_currency:
                amount = partial.amount_currency
            else:
                # For a correct visualization of the amounts, we use the currency rate from the invoice.
                amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id, self.date)
                # INICIO CAMBIO
                if self.company_id.country_id == self.env.ref('base.ar'):
                    if self._fields.get('l10n_ar_currency_rate') and self.l10n_ar_currency_rate and self.l10n_ar_currency_rate != 1.0:
                        amount = self.currency_id.round(abs(partial.amount) / self.l10n_ar_currency_rate)
                # FIN CAMBIO
            if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                continue

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': amount,
                'currency': self.currency_id.symbol,
                'digits': [69, self.currency_id.decimal_places],
                'position': self.currency_id.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        return reconciled_vals

    @api.constrains('state', 'type', 'journal_id')
    def check_invoice_and_journal_type(self, default=None):
        """ Only let to create customer invoices/vendor bills in respective sale/purchase journals """
        error = self.filtered(
            lambda x: x.is_sale_document() and x.journal_id.type != 'sale' or
            x.is_purchase_document() and x.journal_id.type != 'purchase')
        if error:
            raise ValidationError(_(
                'You can create sales/purchase invoices exclusively in the respective sales/purchase journals'))

    def unlink(self):
        """ If we delete a journal entry that is related to a reconcile line then we need to clean the statement line
        in order to be able to reconcile in the future (clean up the move_name field)."""
        self.mapped('line_ids.statement_line_id').write({'move_name': False})
        return super().unlink()

    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        """ Odoo recomputa todos los impuestos cada vez que hay un cambio en la factura, esto trae dos problemas:
        1. Es molesto para los usuarios que, luego de haber cargado las percepciones, quieren hacer una modificacion
        y se les recomputa todo
        2. No podemos agregar de manera facil los impuestos en el modulo account_invoice_tax porque:
        a) si llamamos a _recompute_tax_lines (a traves de _recompute_dynamic_lines) sin recompute_tax_base_amount
        entonces odoo NO crea la nueva linea de impuesto porque escapea antes
        b) si llamamos pasando recompute_tax_base_amount= True entonces se nos recomputa cualquier impuesto previamente
        cargado

        Con esto lo que hacemos es anular el re-calculo de impuestos "fixed". Si dejamos que se recompute el base
        amount
        """
        # if calling with recompute_tax_base_amount then tax amounts are not changed and we can return super directly
        if recompute_tax_base_amount:
            return super()._recompute_tax_lines(recompute_tax_base_amount=recompute_tax_base_amount)
        in_draft_mode = self != self._origin
        fixed_taxes_bu = {
            line: {
                'amount_currency': line.amount_currency,
                'debit': line.debit,
                'credit': line.credit,
            } for line in self.line_ids.filtered(lambda x: x.tax_repartition_line_id.tax_id.amount_type == 'fixed')}

        res = super()._recompute_tax_lines(recompute_tax_base_amount=recompute_tax_base_amount)
        for tax_line in self.line_ids.filtered(
                lambda x: x.tax_repartition_line_id.tax_id.amount_type == 'fixed' and x in fixed_taxes_bu):
            tax_line.update(fixed_taxes_bu.get(tax_line))
            if in_draft_mode:
                tax_line._onchange_amount_currency()
                tax_line._onchange_balance()
        return res
