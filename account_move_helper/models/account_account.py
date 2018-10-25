##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountAccount(models.Model):
    _inherit = "account.account"

    balance = fields.Monetary(
        compute='_compute_balance',
    )
    new_balance = fields.Monetary(
        'Balance',
        compute='_compute_new_balance',
        inverse='_inverse_new_balance'
    )

    @api.depends('balance')
    def _compute_new_balance(self):
        move_id = self._context.get('active_id', False)
        if not move_id:
            return False
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            move_line = AccountMoveLine.search([
                ('move_id', '=', move_id),
                ('account_id', '=', rec.id)], limit=1)
            rec.new_balance = rec.balance + move_line.balance

    @api.multi
    def _compute_balance(self):
        move_id = self._context.get('active_id', False)
        move = self.env['account.move'].browse(move_id)
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            domain = [
                ('account_id', '=', rec.id),
                ('move_id.state', '=', 'posted'),
            ]
            if move:
                domain.append(('date', '<=', move.date))
            rec.balance = sum(AccountMoveLine.search(domain).mapped('balance'))

    @api.multi
    def _inverse_new_balance(self):
        """agregamos el round por un bug de odoo que por mas que estos
        trabajando con x decimales, si el usuario por interfaz agrega mas
        decimales (que x) odoo lo termina almacenando y luego da error
        por descuadre de apunte
        """
        for rec in self:
            new_balance = rec.company_id.currency_id.round(rec.new_balance)
            line_balance = new_balance - rec.balance
            rec._helper_update_line(line_balance)

    @api.multi
    def _helper_update_line(self, line_balance, partner=None):
        """
        * line_balance: balance to be used on the move line related to this
        account
        * value_diff: difference between the actual balance of a line
        (if exists) for this account and the new balance
        * new_balance: balance of the account considering lines on this entry
        * balance: balance for the account without this entry
        """
        move_id = self._context.get('active_id', False)
        if not move_id:
            return True
        move = self.env['account.move'].browse(move_id)

        # TODO improove and use debit or credit regarding balance
        helper_account = (
            move.journal_id.default_debit_account_id or
            move.journal_id.default_credit_account_id)
        if not helper_account:
            raise UserError(_(
                'You need a default debit or credit account configured on '
                'journal "%s".') % (move.journal_id.name))

        line_balance = value_diff = line_balance

        move_line_vals = []

        base_domain = [('move_id', '=', move_id)]
        if partner:
            base_domain.append(('partner_id', '=', partner.id))

        move_line = self.env['account.move.line'].search(
            base_domain + [('account_id', '=', self.id)], limit=1)

        counterpart_move_line = self.env['account.move.line'].search([
            ('move_id', '=', move_id),
            ('account_id', '=', helper_account.id)], limit=1)

        # if there is a move line we get the value_diff
        if move_line:
            if move_line.debit:
                value_diff -= move_line.debit
            elif move_line.credit:
                value_diff += move_line.credit

        if line_balance > 0:
            debit = line_balance
            credit = 0.0
        elif line_balance < 0:
            debit = 0.0
            credit = -line_balance

        # if there is a counterpart line we update values, we unlink if balance
        # become 0
        if counterpart_move_line:
            counterpart_balance = counterpart_move_line.balance - value_diff
            if counterpart_balance > 0:
                counterpart_debit = counterpart_balance
                counterpart_credit = 0.0
            elif counterpart_balance < 0:
                counterpart_debit = 0.0
                counterpart_credit = -counterpart_balance
            if counterpart_balance:
                # update
                move_line_vals.append((1, counterpart_move_line.id, {
                    'credit': counterpart_credit,
                    'debit': counterpart_debit,
                }))
            else:
                # unlink
                move_line_vals.append((3, counterpart_move_line.id, False))
        else:
            # create
            move_line_vals.append((0, False, {
                'name': _('Opening Balance'),
                'account_id': helper_account.id,
                'credit': debit,
                'debit': credit,
            }))

        # if there is a move line we update values, we unlink if balance
        # become 0
        if move_line:
            if line_balance:
                # update
                move_line_vals.append((1, move_line.id, {
                    'credit': credit,
                    'debit': debit,
                }))
            else:
                # unlink
                move_line_vals.append((3, move_line.id, False))
        else:
            # create
            move_line_vals.append((0, False, {
                'name': _('Opening Balance'),
                'account_id': self.id,
                'credit': credit,
                'debit': debit,
                'partner_id': partner and partner.id or False,
            }))

        move.write({'line_ids': move_line_vals})
