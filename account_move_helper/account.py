# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
from ast import literal_eval
from openerp.exceptions import Warning


class account_account(models.Model):
    _inherit = "account.account"

    new_balance = fields.Float(
        'Balance',
        compute='_get_balance',
        inverse='_set_balance')

    @api.one
    @api.depends('balance')
    def _get_balance(self):
        self.new_balance = self.balance

    @api.one
    def _set_balance(self):
        move_id = self._context.get('active_id', False)
        move = self.env['account.move'].browse(move_id)
        if not move.journal_id.centralisation:
            raise Warning(_(
                'You need a Journal with centralisation checked to '
                'set the initial balance.'))

        value_diff = self.new_balance - self.balance
        if not value_diff or not move_id:
            return True
        move_line = self.env['account.move.line'].search(
            [('move_id', '=', move_id), ('account_id', '=', self.id)], limit=1)

        if move_line:
            if move_line.debit:
                value_diff += move_line.debit
            elif move_line.credit:
                value_diff -= move_line.credit

        if value_diff > 0:
            debit = value_diff
            credit = 0.0
        elif value_diff < 0:
            debit = 0.0
            credit = -value_diff

        if move_line:
            if value_diff:
                move_line.write({
                    'credit': credit,
                    'debit': debit,
                    })
            else:
                move_line.unlink()
        else:
            move_line.create({
                'name': _('Opening Balance'),
                'account_id': self.id,
                'move_id': move_id,
                'credit': credit,
                'debit': debit,
                'journal_id': move.journal_id.id,
                'period_id': move.period_id.id,
            })


class account_move(models.Model):
    _inherit = "account.move"

    @api.multi
    def add_account_to_move(self):
        self.ensure_one()
        action_read = False
        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account_move_helper.view_account_journal_tree')
        search_view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account.view_account_search')
        actions = self.env.ref(
            'account.action_account_form')
        if actions:
            action_read = actions.read()[0]
            context = literal_eval(action_read['context'])
            # we send company in context so it filters taxes
            context['company_id'] = self.company_id.id
            action_read['domain'] = [
                ('type', 'in', ['liquidity', 'other']),
                ('company_id', '=', self.company_id.id)]
            # this search view removes pricelist
            action_read.pop("search_view", None)
            action_read['search_view_id'] = (search_view_id, False)
            action_read['view_mode'] = 'tree,form'
            action_read['views'] = [
                (view_id, 'tree'), (False, 'form')]
            action_read['name'] = _('Account')
        return action_read

    @api.multi
    def add_partner_to_move(self):
        self.ensure_one()
        action_read = False
        view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'account_move_helper.view_partner_tree')
        search_view_id = self.env['ir.model.data'].xmlid_to_res_id(
            'base.view_res_partner_filter')
        actions = self.env.ref(
            'base.action_partner_form')
        if actions:
            action_read = actions.read()[0]
            context = literal_eval(action_read['context'])
            # we send company in context so it filters taxes
            context['company_id'] = self.company_id.id
            # this search view removes pricelist
            action_read.pop("search_view", None)
            action_read['search_view_id'] = (search_view_id, False)
            action_read['view_mode'] = 'tree,form'
            action_read['views'] = [
                (view_id, 'tree'), (False, 'form')]
            action_read['name'] = _('Partners')
        return action_read
