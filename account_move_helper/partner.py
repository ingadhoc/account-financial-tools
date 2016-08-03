# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _


class res_partner(models.Model):
    _inherit = "res.partner"

    @api.multi
    @api.depends('credit', 'debit')
    def _get_credit_debit_get(self):
        res = super(res_partner, self)._credit_debit_get(
            field_names=['credit', 'debit'], arg=None)
        for partner in self:
            partner.new_credit = res[partner.id]['credit']
            partner.new_debit = res[partner.id]['debit']
        return res

    @api.one
    def _set_new_debit(self):
        self._set_new_credit_debit('debit', 'property_account_payable')

    @api.one
    def _set_new_credit(self):
        self._set_new_credit_debit('credit', 'property_account_receivable')

    @api.multi
    def _set_new_credit_debit(self, field, account_field):
        move_id = self._context.get('active_id', False)
        move = self.env['account.move'].browse(move_id)
        if not move_id:
            return True
        if not move.journal_id.centralisation:
            raise Warning(_(
                'You need a Journal with centralisation checked to '
                'set the initial balance.'))

        new_value = getattr(self, 'new_%s' % field)
        value_diff = new_value - getattr(self, field)
        account = getattr(
            self.with_context(force_company=move.company_id.id),
            account_field)
        move_line = self.env['account.move.line'].search([
            ('move_id', '=', move_id),
            ('partner_id', '=', self.id),
            ('account_id', '=', account.id)], limit=1)

        if field == 'debit':
            value_diff = -value_diff
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
        elif value_diff:
            move_line.create({
                'name': _('Opening Balance'),
                'account_id': account.id,
                'move_id': move_id,
                'credit': credit,
                'debit': debit,
                'partner_id': self.id,
                'journal_id': move.journal_id.id,
                'period_id': move.period_id.id,
            })

    new_credit = fields.Float(
        'Total Receivable',
        compute='_get_credit_debit_get',
        inverse='_set_new_credit',
    )

    new_debit = fields.Float(
        'Total Payable',
        compute='_get_credit_debit_get',
        inverse='_set_new_debit',
    )
