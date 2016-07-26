# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields, _
from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gral_domain = [('reconcile_id', '=', False)]
    receivable_domain = gral_domain + [('type', '=', 'receivable')]
    payable_domain = gral_domain + [('type', '=', 'payable')]

    receivable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=receivable_domain,
    )
    payable_debt_ids = fields.One2many(
        'account.debt.line',
        'partner_id',
        domain=payable_domain,
    )
    debt_balance = fields.Float(
        compute='_get_debt_balance',
    )

    @api.multi
    def _get_debt_lines(self):
        self.ensure_one()
        result_selection = self._context.get('result_selection', False)
        if result_selection == 'receivable':
            domain = self.receivable_domain
        elif result_selection == 'payable':
            domain = self.payable_domain
        else:
            domain = self.gral_domain
        domain += [('partner_id', '=', self.id)]
        return self.env['account.debt.line'].search(domain)

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
