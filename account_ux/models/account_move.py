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

        for rec in self.filtered(lambda x: x.is_invoice(include_receipts=True) and x.journal_id.mail_template_id):
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

    @api.onchange('partner_id')
    def _onchange_partner_commercial(self):
        if self.partner_id.user_id:
            self.user_id = self.partner_id.user_id.id

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

    @api.constrains('state', 'type', 'journal_id')
    def check_invoice_and_journal_type(self, default=None):
        """ Only let to create customer invoices/vendor bills in respective sale/purchase journals """
        error = self.filtered(
            lambda x: x.is_sale_document() and x.journal_id.type != 'sale' or
            not x.is_sale_document() and x.journal_id.type == 'sale' or
            x.is_purchase_document() and x.journal_id.type != 'purchase' or
            not x.is_purchase_document() and x.journal_id.type == 'purchase')
        if error:
            raise ValidationError(_(
                'You can create sales/purchase invoices exclusively in the respective sales/purchase journals'))
