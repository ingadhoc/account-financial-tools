# flake8: noqa
import json
from odoo.tools import float_is_zero
from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError


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

    # def _compute_payments_widget_to_reconcile_info(self):
    #     for move in self:
    #         move.invoice_outstanding_credits_debits_widget = json.dumps(False)
    #         move.invoice_has_outstanding = False

    #         if move.state != 'posted' \
    #                 or move.payment_state not in ('not_paid', 'partial') \
    #                 or not move.is_invoice(include_receipts=True):
    #             continue

    #         pay_term_lines = move.line_ids\
    #             .filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))

    #         domain = [
    #             ('account_id', 'in', pay_term_lines.account_id.ids),
    #             ('move_id.state', '=', 'posted'),
    #             ('partner_id', '=', move.commercial_partner_id.id),
    #             ('reconciled', '=', False),
    #             '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
    #         ]

    #         payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

    #         if move.is_inbound():
    #             domain.append(('balance', '<', 0.0))
    #             payments_widget_vals['title'] = _('Outstanding credits')
    #         else:
    #             domain.append(('balance', '>', 0.0))
    #             payments_widget_vals['title'] = _('Outstanding debits')

    #         for line in self.env['account.move.line'].search(domain):

    #             if line.currency_id == move.currency_id:
    #                 # Same foreign currency.
    #                 amount = abs(line.amount_residual_currency)
    #             else:
    #                 # Different foreign currencies.
    #                 # INICIO CAMBIO
    #                 # as we dont add the currency information we use the rate of the invoice that is the one used by odoo compute amount_residual
    #                 if move.company_id.country_id == self.env.ref('base.ar'):
    #                     amount =  move.company_currency_id._convert(
    #                         abs(line.amount_residual),
    #                         move.currency_id,
    #                         move.company_id,
    #                         move.invoice_date or fields.Date.today(),
    #                     )
    #                 else:
    #                     amount =  move.company_currency_id._convert(
    #                         abs(line.amount_residual),
    #                         move.currency_id,
    #                         move.company_id,
    #                         line.date or fields.Date.today(),
    #                     )
    #                 # FIN CAMBIO

    #             if move.currency_id.is_zero(amount):
    #                 continue

    #             payments_widget_vals['content'].append({
    #                 'journal_name': line.ref or line.move_id.name,
    #                 'amount': amount,
    #                 'currency': move.currency_id.symbol,
    #                 'id': line.id,
    #                 'move_id': line.move_id.id,
    #                 'position': move.currency_id.position,
    #                 'digits': [69, move.currency_id.decimal_places],
    #                 'payment_date': fields.Date.to_string(line.date),
    #             })

    #         if not payments_widget_vals['content']:
    #             continue

    #         move.invoice_outstanding_credits_debits_widget = json.dumps(payments_widget_vals)
    #         move.invoice_has_outstanding = True

    @api.constrains('state', 'move_type', 'journal_id')
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

    def _recompute_tax_lines(self, recompute_tax_base_amount=False, tax_rep_lines_to_recompute=None):
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
            return super()._recompute_tax_lines(recompute_tax_base_amount=recompute_tax_base_amount, tax_rep_lines_to_recompute=tax_rep_lines_to_recompute)
        in_draft_mode = self != self._origin
        fixed_taxes_bu = {
            line: {
                'amount_currency': line.amount_currency,
                'debit': line.debit,
                'credit': line.credit,
            } for line in self.line_ids.filtered(lambda x: x.tax_repartition_line_id.tax_id.amount_type == 'fixed')}

        res = super()._recompute_tax_lines(recompute_tax_base_amount=recompute_tax_base_amount, tax_rep_lines_to_recompute=tax_rep_lines_to_recompute)
        for tax_line in self.line_ids.filtered(
                lambda x: x.tax_repartition_line_id.tax_id.amount_type == 'fixed' and x in fixed_taxes_bu):
            tax_line.update(fixed_taxes_bu.get(tax_line))
            if in_draft_mode:
                tax_line._onchange_amount_currency()
                tax_line._onchange_balance()
        return res
