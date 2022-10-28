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
