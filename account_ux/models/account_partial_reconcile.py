from odoo import models, api


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model
    def create(self, vals):
        """ ademas de mandar en el contexto en el metodo reconcile, hacemos
        que el partial reconcile que crea el metodo auto_reconcile_lines
        no tenga moneda en la misma situación (podriamos ).
        Va de la mano de la modificacion de "def reconcile" en aml
        """
        if vals.get('currency_id'):
            account = self.env['account.move.line'].browse(vals.get('debit_move_id')).account_id
            if account.company_id.country_id == self.env.ref('base.ar') and not account.currency_id:
                vals.update({'currency_id': False, 'amount_currency': 0.0})
        return super().create(vals)
