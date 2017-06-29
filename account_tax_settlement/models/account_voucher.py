# -*- coding: utf-8 -*-
from openerp import fields, api, models, _


class account_voucher(models.Model):
    _inherit = 'account.voucher'

    tax_move_line_ids = fields.One2many(
        'account.move.line',
        compute='_get_tax_move_lines',
        string=_('Tax Journal Items'),
    )

    @api.one
    @api.depends(
        'move_id.line_id.tax_code_id',
        'move_id.line_id.tax_amount',
    )
    def _get_tax_move_lines(self):
        self.tax_move_line_ids = self.move_id.line_id.filtered(
            lambda r: r.tax_code_id and r.tax_amount)

    @api.multi
    def cancel_voucher(self):
        """
        We search all move lines that has been settled for vouchers and, after
        unreconcile, we try to unlink them. If one tax settlement has been paid
        or has been settled on a settlement, then won't allow you to cancel the
        voucher.
        """
        tax_settlement_moves = self.mapped('move_ids.tax_settlement_move_id')
        res = super(account_voucher, self).cancel_voucher()
        tax_settlement_moves.unlink()
        return res
