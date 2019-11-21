# flake8: noqa
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api


class ResPartner(models.Model):

    _inherit = "res.partner"

    @api.multi
    def _credit_debit_get(self):
        # pylint: disable=E8103
        tables, where_clause, where_params = self.env['account.move.line']._query_get()
        # child_companies = self.env.user.company_id.child_ids
        # TODO habria que mejorarlo y evitar esta consulta adicional
        child_companies = self.env['res.company'].search(
            [('id', 'child_of', self.env.user.company_id.id)])
        where_params = [tuple(self.ids)] + [
            tuple(child_companies.ids)] + where_params
        if where_clause:
            where_clause = 'AND ' + where_clause
        self._cr.execute("""SELECT account_move_line.partner_id, act.type, SUM(account_move_line.amount_residual)
                      FROM account_move_line
                      LEFT JOIN account_account a ON (account_move_line.account_id=a.id)
                      LEFT JOIN account_account_type act ON (a.user_type_id=act.id)
                      WHERE act.type IN ('receivable','payable')
                      AND account_move_line.partner_id IN %s
                      AND account_move_line.reconciled IS FALSE
                      AND account_move_line.company_id IN %s
                      """ + where_clause + """
                      GROUP BY account_move_line.partner_id, act.type
                      """, where_params)
        for pid, _type, val in self._cr.fetchall():
            partner = self.browse(pid)
            if _type == 'receivable':
                partner.credit = val
            elif _type == 'payable':
                partner.debit = -val

    @api.multi
    def _asset_difference_search(self, account_type, operator, operand):
        if operator not in ('<', '=', '>', '>=', '<='):
            return []
        if type(operand) not in (float, int):
            return []
        sign = 1
        if account_type == 'payable':
            sign = -1
        # We add to filter by childs companies if you are in parent company
        child_companies = self.env['res.company'].search(
            [('id', 'child_of', self.env.user.company_id.id)])
        res = self._cr.execute('''
            SELECT partner.id
            FROM res_partner partner
            LEFT JOIN account_move_line aml ON aml.partner_id = partner.id
            RIGHT JOIN account_account acc ON aml.account_id = acc.id
            WHERE acc.internal_type = %s
              AND NOT acc.deprecated AND acc.company_id IN %s
            GROUP BY partner.id
            HAVING %s * COALESCE(SUM(aml.amount_residual), 0) ''' + operator + ''' %s''', (
                account_type, tuple(child_companies.ids), sign, operand))
        res = self._cr.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [r[0] for r in res])]
