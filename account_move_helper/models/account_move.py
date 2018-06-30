##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _


class AccountMove(models.Model):
    _inherit = "account.move"

    move_helper_enable = fields.Boolean(
        compute='_compute_move_helper_enable',
    )

    @api.depends(
        'journal_id.type',
        'journal_id.default_credit_account_id',
        'journal_id.default_debit_account_id',
    )
    def _compute_move_helper_enable(self):
        for rec in self:
            if rec.journal_id.type == 'general' \
                    and rec.journal_id.default_debit_account_id \
                    and rec.journal_id.default_credit_account_id:
                rec.move_helper_enable = True

    @api.multi
    def add_account_to_move(self):
        self.ensure_one()
        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account_move_helper.view_account_helper_tree')
        search_view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account.view_account_search')

        return {
            'name': _('Accounts'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'account.account',
            'view_id': view_id,
            'search_view_id': search_view_id,
            'target': 'current',
            'domain': [
                ('internal_type', 'in', ['liquidity', 'other']),
                ('company_id', '=', self.company_id.id),
                ('deprecated', '=', False)],
            'context': {'company_id': self.company_id.id},
        }

    @api.multi
    def add_partner_to_move(self):
        self.ensure_one()
        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account_move_helper.view_partner_helper_tree')
        search_view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'base.view_res_partner_filter')

        return {
            'name': _('Partners'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'res.partner',
            'view_id': view_id,
            'search_view_id': search_view_id,
            'target': 'current',
            # only commercial partners
            'domain': [
                '|', ('parent_id', '=', False), ('is_company', '=', True)],
            'context': {'company_id': self.company_id.id},
        }
