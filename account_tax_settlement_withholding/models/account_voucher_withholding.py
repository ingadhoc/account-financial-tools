# -*- coding: utf-8 -*-
from openerp import api, models, fields


class account_voucher_withholding(models.Model):
    _inherit = 'account.voucher.withholding'

    tax_state = fields.Selection(
        related='move_line_id.tax_state',
        readonly=True,
        )

    @api.multi
    def pay_tax_settlement(self):
        self.ensure_one()
        return self.move_line_id.tax_settlement_move_id.with_context(
            from_settlement=True).create_voucher('payment')

    @api.multi
    def make_tax_settlement(self):
        self.ensure_one()
        return self.move_line_id.make_tax_settlement()
