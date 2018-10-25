##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # TODO recreamos credit_copy y debit_copy porque odo da error si mandamos
    # company_id =.. en el conexto, termina arrojando:
    # ("account_move_line"."company_id" = (1
    credit_copy = fields.Monetary(
        'Credit',
        compute='_compute_debit_credit',
    )
    debit_copy = fields.Monetary(
        'Debit',
        compute='_compute_debit_credit',
    )
    new_credit = fields.Monetary(
        compute='_compute_new_debit_credit',
        inverse='_inverse_new_credit'
    )
    new_debit = fields.Monetary(
        compute='_compute_new_debit_credit',
        inverse='_inverse_new_debit'
    )

    @api.multi
    def _compute_new_debit_credit(self):
        move_id = self._context.get('active_id', False)
        AccountMoveLine = self.env['account.move.line']
        if not move_id:
            return False
        company_id = self._context.get(
            'company_id',
            self.env.user.company_id.id)

        for rec in self:
            for account_field, field, from_field in [
                    ('property_account_receivable_id',
                        'new_credit', 'credit_copy'),
                    ('property_account_payable_id',
                        'new_debit', 'debit_copy')]:
                account = getattr(
                    rec.with_context(force_company=company_id), account_field)
                move_line = AccountMoveLine.search([
                    ('move_id', '=', move_id),
                    ('partner_id', '=', rec.id),
                    ('account_id', '=', account.id),
                ], limit=1)
                rec[field] = rec[from_field] + move_line.balance

    @api.multi
    def _compute_debit_credit(self):
        move_id = self._context.get('active_id', False)
        move = self.env['account.move'].browse(move_id)
        company_id = self._context.get('company_id', False)
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            for internal_type, field in [
                    ('receivable', 'credit_copy'), ('payable', 'debit_copy')]:
                domain = [
                    ('partner_id', '=', rec.id),
                    # not reconciled for performance
                    ('reconciled', '=', False),
                    ('account_id.internal_type', '=', internal_type),
                    ('move_id.state', '=', 'posted'),
                ]
                if company_id:
                    domain.append(('company_id', '=', company_id))
                if move:
                    domain.append(('date', '<=', move.date))
                rec[field] = sum(
                    AccountMoveLine.search(domain).mapped('balance'))

    @api.multi
    def _inverse_new_debit(self):
        self._set_new_credit_debit(
            'new_debit', 'debit_copy', 'property_account_payable_id')

    @api.multi
    def _inverse_new_credit(self):
        self._set_new_credit_debit(
            'new_credit', 'credit_copy', 'property_account_receivable_id')

    @api.multi
    def _set_new_credit_debit(
            self, new_value_field, old_value_field, account_field):
        company_id = self._context.get('company_id', False)
        if not company_id:
            raise UserError(_(
                'Company is required in context to set partner balance'))
        for rec in self:
            account = getattr(
                rec.with_context(force_company=company_id), account_field)
            new_value = rec[new_value_field] or 0.0
            value_diff = new_value - (rec[old_value_field] or 0.0)
            account._helper_update_line(value_diff, rec)
