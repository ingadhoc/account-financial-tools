from odoo import models, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

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
            raise ValidationError(_(
                "Some move lines don't have analytic tags and "
                "analytic tags are required by the account type.\n"
                "* Accounts: %s\n"
                "* Move lines ids: %s" % (
                    ", ".join(move_lines.mapped('account_id.name')),
                    move_lines.ids
                )
            ))

        # After validate invoice will sent an email to the partner if the related journal has mail_template_id set.
        res = super(AccountMove, self).post()
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

    @api.onchange('invoice_date')
    def onchange_invoice_date(self):
        if self.date:
            return {'warning': {
                'title': _("Warning!"),
                'message': _(
                    'You are changing the Invoice Date but you have force an '
                    'accounting date.\n Please check if you need to update '
                    'the accounting date too.')}}

    def copy(self, default=None):
        res = super().copy(default=default)
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
