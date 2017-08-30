# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import models, api


class ResPartner(models.Model):

    _inherit = "res.partner"

    @api.multi
    def _credit_debit_get(self):
        """
        We over write this function to filter moves by company id
        because if not a user on a child company see the debt of for all
        comapnies. We have try using context with company id but it does not
        works
        """
        tables, where_clause, where_params = self.env[
            'account.move.line']._query_get()
        # child_companies = self.env.user.company_id.child_ids
        child_companies = self.env['res.company'].search(
            [('id', 'child_of', self.env.user.company_id.id)])
        where_params = [tuple(self.ids)] + [
            tuple(child_companies.ids)] + where_params
        if where_clause:
            where_clause = 'AND ' + where_clause
        self._cr.execute("""
            SELECT account_move_line.partner_id, act.type,
                SUM(account_move_line.amount_residual)
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
        for pid, type, val in self._cr.fetchall():
            partner = self.browse(pid)
            if type == 'receivable':
                partner.credit = val
            elif type == 'payable':
                partner.debit = -val
