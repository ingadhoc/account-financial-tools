# -*- coding: utf-8 -*-
from openerp import fields, models, api
# from openerp.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='Settlement Journal',
        compute='_compute_settlement_journal',
    )

    @api.multi
    @api.depends('tag_ids')
    def _compute_settlement_journal(self):
        for rec in self:
            rec.settlement_journal_id = rec.env['account.journal'].search(
                [('settlement_account_tag_ids', 'in', rec.tag_ids.ids)],
                limit=1)
