# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp


class AccountAccount(models.Model):
    _inherit = 'account.account'

    restrict_balance = fields.Boolean(
        'Restrict Balance?',
        digits=dp.get_precision('Account'),
    )
    min_balance = fields.Float(
        'Minimum Balance',
        digits=dp.get_precision('Account'),
    )


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.multi
    # def _post_validate(self):
    def post(self):
        """
        We check that there is enaught balance.
        Now we check on post so we get balance considering this move lines also
        (because first we post and later we check).
        Before we use _post_validate method that is called from other places
        too
        """
        res = super(AccountMove, self).post()
        for move in self:
            for line in move.line_ids.filtered('account_id.restrict_balance'):
                balance = sum(self.env['account.move.line'].search([
                    ('account_id', '=', line.account_id.id),
                    ('move_id.state', '=', 'posted'),
                ]).mapped('balance'))
                if balance < line.account_id.min_balance:
                    raise UserError(_(
                        'Can not create move as account %s balance would be %s'
                        ' and account has restriction of min balance to %s'
                    ) % (
                        line.account_id.name,
                        balance,
                        line.account_id.min_balance))
        # return super(AccountMove, self)._post_validate()
        return res
