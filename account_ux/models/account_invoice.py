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
        super(AccountInvoice, self)._compute_amount()
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_untaxed_signed_real = self.amount_untaxed * sign

    @api.multi
    def invoice_cancel_from_done(self):
        for rec in self:
            if not rec.payment_move_line_ids and rec.state == 'paid':
                rec.action_cancel()

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        res = super(AccountInvoice, self)._onchange_partner_id()
        if self.partner_id and self.partner_id.user_id:
            self.user_id = self.partner_id.user_id.id
        else:
            self.user_id = self.env.uid
        return res
