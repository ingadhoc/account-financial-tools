from odoo import models, api
from odoo.osv import expression


class AccountReconciliation(models.AbstractModel):

    _inherit = 'account.reconciliation.widget'

    @api.multi
    def _prepare_move_lines(
            self, move_lines, target_currency=False, target_date=False,
            recs_count=0):
        """ Show and allow to search by move display name (Document number) on bank statements and partner debt
        reconcile """
        res = super()._prepare_move_lines(
            move_lines, target_currency=target_currency,
            target_date=target_date, recs_count=recs_count)

        for rec in res:
            line = self.env['account.move.line'].browse(rec['id'])
            display_name = line.move_id.display_name or ''
            rec['name'] = line.name and line.name != '/' and display_name + ': ' + line.name or display_name
        return res

    @api.model
    def _domain_move_lines(self, search_str):
        """ Add move display name in search of move lines"""
        _super = super()
        _get_domain = _super._domain_move_lines
        domain = _get_domain(search_str)
        if not search_str and search_str != '/':
            return domain
        domain_trans_ref = [('move_id.display_name', 'ilike', search_str)]
        return expression.OR([domain, domain_trans_ref])
