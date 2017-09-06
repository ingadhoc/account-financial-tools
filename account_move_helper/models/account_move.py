# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, api, _


class AccountMove(models.Model):
    _inherit = "account.move"

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
                ('company_id', '=', self.company_id.id)],
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
            'context': {'company_id': self.company_id.id},
        }
