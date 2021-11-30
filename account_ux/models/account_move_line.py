# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_compare
from datetime import date


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    user_id = fields.Many2one(
        string='Contact Salesperson', related='partner_id.user_id', store=True,
        help='Salesperson of contact related to this journal item')

    def get_model_id_and_name(self):
        # Function used to display the right action on journal
        # items on dropdown lists, in reports like general ledger
        if self.statement_id:
            return ['account.bank.statement', self.statement_id.id, _('View Bank Statement'), False]
        if self.payment_id:
            return ['account.payment', self.payment_id.id, _('View Payment'), False]
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

    # TODO verificar donde tendria que ir este cambio
    # def _reconcile_lines(self, debit_moves, credit_moves, field):
    #     """ Modificamos contexto para que odoo solo concilie el metodo
    #     auto_reconcile_lines teniendo en cuenta la moneda de cia si la cuenta
    #     no tiene moneda.
    #     Va de la mano de la modificación de "create" en
    #     account.partial.reconcile
    #     Para que este cambio funcione bien es ademas importante este parche en odoo
    #     https://github.com/odoo/odoo/pull/63390
    #     """
    #     if self and self[0].company_id.country_id == self.env.ref('base.ar') and not self[0].account_id.currency_id:
    #         field = 'amount_residual'
    #     return super()._reconcile_lines(debit_moves, credit_moves, field)

    # def _prepare_reconciliation_partials(self):
    #     print ('aaaaaaaaa')
    #     backup = {line: line.currency_id for line in self}
    #     self.currency_id = False
    #     res = super()._prepare_reconciliation_partials()
    #     for line in self:
    #         line.currency_id = backup[line]
    #     return res

    # # TODO verificar si lo queremos mantener
    # def reconcile(self):
    #     """ This is needed if you reconcile, for eg, 1 USD to 1 USD but in an ARS account, by default
    #     odoo make a full reconcile and exchange
    #     """
    #     if self and self[0].company_id.country_id == self.env.ref('base.ar') and not self[0].account_id.currency_id:
    #         self = self.with_context(no_exchange_difference=True)
    #     return super().reconcile()
