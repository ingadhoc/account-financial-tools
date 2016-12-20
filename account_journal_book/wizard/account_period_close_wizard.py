# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from openerp import api, fields, models, _


class AccountPeriodClose(models.TransientModel):
    _inherit = "account.period.close"

    @api.model
    def _get_sequence_id(self):
        periods = self.env['account.period'].browse(
            self._context.get('active_ids', []))
        if not periods:
            raise ValidationError(_('No periods selected'))
        elif len(periods.mapped('company_id')) > 1:
            raise ValidationError(_('All periods must belong to same company'))
        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'journal.book.sequence'),
            ('company_id', '=', periods[0].company_id.id),
            ], limit=1)
        if not sequence:
            sequence = sequence.search([
                ('code', '=', 'journal.book.sequence')
                ], limit=1)
        return sequence

    sequence_id = fields.Many2one(
        'ir.sequence',
        'Book Number Sequence',
        domain=[('code', '=', 'journal.book.sequence')],
        context={'default_code': 'journal.book.sequence'},
        help='If no sequence provided then it wont be numbered',
        default=_get_sequence_id,
        )
    next_number = fields.Integer(
        # 'Next Number'
        related='sequence_id.number_next_actual',
        readonly=True,
        )

    # @api.onchange('sequence_id')
    # def onchange_sequence(self):
    #     self.next_number = self.sequence_id.number_next_actual

    # @api.multi
    # def data_save(self):
    #     self.ensure_one()
    #     for period in self.env['account.period'].browse(
    #             self._context.get('active_ids', [])):
    #     return super(AccountPeriodClose, self).data_save()
