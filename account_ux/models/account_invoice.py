##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


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
        res = super(AccountInvoice, self). action_invoice_open()
        for rec in self.filtered('journal_id.mail_template_id'):
            rec.message_post_with_template(
                rec.journal_id.mail_template_id.id,
            )
        return res
