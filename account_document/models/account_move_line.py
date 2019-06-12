from odoo import models, api, fields
# from odoo.exceptions import UserError
from odoo.osv import expression


class AccountMoveLine(models.Model):
    """
    Show and allow to search by move display name (Document number) on
    bank statements and partner debt reconcile
    """

    _inherit = 'account.move.line'

    # useful to group by this field
    document_type_id = fields.Many2one(
        related='move_id.document_type_id',
        readonly=True,
        auto_join=True,
        # stored required to group by
        store=True,
        index=True,
    )

    @api.multi
    def _prepare_move_lines(
            self, move_lines, target_currency=False, target_date=False,
            recs_count=0):
        res = super(
            AccountMoveLine,
            self).prepare_move_lines_for_reconciliation_widget(
            move_lines, target_currency=target_currency,
            target_date=target_date, recs_count=recs_count)
        for rec in res:
            line = self.browse(rec['id'])
            display_name = line.move_id.display_name or ''
            rec['name'] = (
                line.name and line.name != '/' and
                display_name + ': ' + line.name or
                display_name)
        return res

    @api.model
    def _domain_move_lines(self, search_str):
        """ Add move display name in search of move lines"""
        _super = super(AccountMoveLine, self)
        _get_domain = _super._domain_move_lines
        domain = _get_domain(search_str)
        if not search_str and search_str != '/':
            return domain
        domain_trans_ref = [('move_id.display_name', 'ilike', search_str)]
        return expression.OR([domain, domain_trans_ref])
