##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _


class AccountChangeCurrency(models.TransientModel):
    _name = 'account.change.currency'
    _description = 'Change Currency'

    @api.model
    def get_move(self):
        move = self.env['account.move'].browse(
            self._context.get('active_id', False))
        return move

    currency_from_id = fields.Many2one(
        'res.currency',
        string='Currency From',
        related='move_id.currency_id',
        help="Currency from Invoice"
    )
    currency_to_id = fields.Many2one(
        'res.currency',
        string='Currency to',
        required=True,
        help="Select a currency to apply on the invoice",
    )
    currency_rate = fields.Float(
        'Currency Rate',
        required=True,
        help="Select a rate to apply on the invoice"
    )
    move_id = fields.Many2one(
        'account.move',
        default=get_move
    )

    change_type = fields.Selection(
        [('currency', 'Change Only Currency'),
         ('value', 'Update both currency and values')],
        default='currency'
    )

    @api.onchange('currency_to_id')
    def onchange_currency(self):
        if not self.currency_to_id:
            self.currency_rate = False
        else:
            currency = self.currency_from_id.with_context(
                )
            self.currency_rate = currency._convert(
                1.0, self.currency_to_id, self.move_id.company_id,
                date=self.move_id.invoice_date or
                fields.Date.context_today(self))

    def change_currency(self):
        self.ensure_one()
        if self.change_type == 'currency':
            self.currency_rate = 1
        message = _("Currency changed from %s to %s with rate %s") % (
            self.move_id.currency_id.name, self.currency_to_id.name,
            self.currency_rate)
        for line in self.move_id.invoice_line_ids:
            # do not round on currency digits, it is rounded automatically
            # on price_unit precision
            line.price_unit = line.price_unit * self.currency_rate
        self.move_id.currency_id = self.currency_to_id.id

        # # update manual taxes
        # for line in self.move_id.tax_line_ids.filtered(lambda x: x.manual):
        #     line.amount = self.currency_to_id.round(
        #         line.amount * self.currency_rate)

        # self.move_id.compute_taxes()
        # self.move_id._onchange_recompute_dynamic_lines()

        self.move_id.message_post(body=message)
        return {'type': 'ir.actions.act_window_close'}
