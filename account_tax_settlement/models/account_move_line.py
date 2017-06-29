# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # a este lo dejamos por ahora pero tal vez podamos evitarlo
    # igual me quiero simplificar no usando la conciliacion por ahora
    tax_settlement_move_id = fields.Many2one(
        'account.move',
        'Tax Settlement Move',
        help='Move where this tax has been settled',
    )

    @api.multi
    def _get_tax_settlement_journal(self):
        """
        This method return the journal that can settle this move line.
        This can be overwrited by other modules
        """
        self.ensure_one()
        return self.account_id.settlement_journal_id
        # return self.env['account.journal']

    @api.multi
    def create_tax_settlement_entry(self):
        settlement_journal = self.env['account.journal']
        for rec in self:
            settlement_journal |= rec._get_tax_settlement_journal()
        if not settlement_journal:
            raise ValidationError(_(
                'No encontramos diario de liquidación para los apuntes '
                'contables: %s') % self.ids)
        elif len(settlement_journal) != 1:
            raise ValidationError(_(
                'Solo debe seleccionar líneas que se liquiden con un mismo '
                'diario, las líneas seleccionadas (ids %s) se liquidan con '
                'diarios %s') % (self.ids, settlement_journal.ids))
        settlement_journal.create_tax_settlement_entry(self)

    tax_state = fields.Selection([
        ('to_settle', 'To Settle'),
        ('to_pay', 'To Pay'),
        ('paid', 'Paid'),
    ],
        'Tax State',
        compute='_compute_tax_state',
        store=True,
    )

    @api.multi
    @api.depends(
        'tax_line_id',
        'tax_settlement_move_id.matched_percentage',
    )
    def _compute_tax_state(self):
        for rec in self.filtered(lambda x: x.tax_line_id):
            # en los moves existe matched_percentage que es igual a 1
            # cuando se pago completamente
            if rec.tax_settlement_move_id.matched_percentage == 1.0:
                state = 'paid'
            elif rec.tax_settlement_move_id:
                state = 'to_pay'
            else:
                state = 'to_settle'
            rec.tax_state = state

    @api.multi
    def action_open_tax_settlement_entry(self):
        self.ensure_one()
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'res_id': self.tax_settlement_move_id.id,
            'type': 'ir.actions.act_window',
        }

    @api.multi
    def action_pay_tax_settlement(self):
        self.ensure_one()
        open_move_line_ids = self.tax_settlement_move_id.line_ids.filtered(
            lambda r: not r.reconciled and r.account_id.internal_type in (
                'payable', 'receivable'))
        return {
            'name': _('Register Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment.group',
            'view_id': False,
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'to_pay_move_line_ids': open_move_line_ids.ids,
                'pop_up': True,
                'default_company_id': self.company_id.id,
            },
        }
