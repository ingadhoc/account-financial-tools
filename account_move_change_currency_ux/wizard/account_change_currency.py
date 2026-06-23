from odoo import _, api, fields, models
from odoo.tools.misc import formatLang
from markupsafe import Markup


class AccountChangeCurrency(models.TransientModel):
    _inherit = 'account.change.currency'

    inverse_currency_rate = fields.Float(
        'Inverse Currency Rate',
        digits=(16, 10),
        help="1 / Currency Rate",
    )

    @api.onchange('currency_to_id')
    def onchange_currency(self):
        result = super().onchange_currency()
        if self.conversion_rate:
            self.inverse_currency_rate = 1 / self.conversion_rate
        else:
            self.inverse_currency_rate = False
        return result

    @api.onchange('conversion_rate')
    def _onchange_conversion_rate(self):
        if self.conversion_rate:
            self.inverse_currency_rate = 1 / self.conversion_rate
        else:
            self.inverse_currency_rate = False

    @api.onchange('inverse_currency_rate')
    def _onchange_inverse_currency_rate(self):
        if self.inverse_currency_rate:
            self.conversion_rate = 1 / self.inverse_currency_rate
        else:
            self.conversion_rate = False

    def change_currency(self):
        self.ensure_one()
        move = self.move_id
        if self.currency_to_id == move.currency_id:
            return {'type': 'ir.actions.act_window_close'}

        old_amount_untaxed = move.amount_untaxed
        res = super().change_currency()

        # Build narration and chatter messages
        if self.conversion_rate >= 1:
            previous_currency = move.currency_id
            rate = self.conversion_rate
        else:
            previous_currency = self.currency_to_id
            rate = 1 / self.conversion_rate
        message = _("|| Original or Previous quotation in {0}. Rate: {1}").format(
            previous_currency.name, formatLang(self.env, rate, currency_obj=move.company_id.currency_id))
        if '||' in str(move.narration):
            move.narration = move.narration[:move.narration.find('||')] + message
        else:
            move.narration = '{0} {1}'.format(move.narration or '', message)

        body = '{message1}. {message2}: {message3}'.format(
            message1=message.split(". ")[1],
            message2=_('Original or Previous Untaxed Amount'),
            message3=formatLang(self.env, old_amount_untaxed, currency_obj=move.currency_id)
        )
        body += Markup('<br />') + _('Calculated Untaxed Amount: {}').format(
            formatLang(self.env, move.amount_untaxed, currency_obj=move.currency_id))
        move.message_post(body=body)

        return res
