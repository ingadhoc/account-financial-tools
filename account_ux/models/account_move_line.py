# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, _
# from collections import OrderedDict
# from odoo.tools import float_compare, float_is_zero


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_model_id_and_name(self):
        # Function used to display the right action on journal
        # items on dropdown lists, in reports like general ledger
        if self.statement_id:
            return ['account.bank.statement',
                    self.statement_id.id, _('View Bank Statement'), False]
        if self.payment_id:
            return ['account.payment',
                    self.payment_id.id, _('View Payment'), False]
        return ['account.move', self.move_id.id, _('View Move'), False]

    def action_open_related_document(self):
        self.ensure_one()
        # usamos lo que ya se usa en js para devolver la accion
        res_model, res_id, action_name, view_id = self.get_model_id_and_name()

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_id': res_id,
        }

    @api.multi
    def _reconcile_lines(self, debit_moves, credit_moves, field):
        """ Modificamos contexto para que odoo solo concilie el metodo
        auto_reconcile_lines teniendo en cuenta la moneda de cia si la cuenta
        no tiene moneda.
        Va de la mano de la modificación de "create" en
        account.partial.reconcile
        """
        if not self[0].account_id.currency_id:
            field = 'amount_residual'
        return super()._reconcile_lines(debit_moves, credit_moves, field)
