# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields, _
from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gral_domain = [('reconciled', '=', False)]
    # gral_domain = [
    #     ('reconcile_id', '=', False),
    #     ('account_id.active', '=', True),
    #     ('state', '!=', 'draft')]
    # receivable_domain = gral_domain + [('account_id.type', '=', 'receivable')]
    # payable_domain = gral_domain + [('account_id.type', '=', 'payable')]
    receivable_domain = gral_domain + [('type', '=', 'receivable')]
    payable_domain = gral_domain + [('type', '=', 'payable')]

    # now we use account.debt.summary
    receivable_debt_ids = fields.One2many(
        'account.debt.summary',
        'partner_id',
        domain=receivable_domain,
    )
    payable_debt_ids = fields.One2many(
        'account.debt.summary',
        'partner_id',
        domain=payable_domain,
    )
    # receivable_line_ids = fields.One2many(
    #     'account.move.line',
    #     'partner_id',
    #     domain=receivable_domain,
    # )
    # payable_line_ids = fields.One2many(
    #     'account.move.line',
    #     'partner_id',
    #     domain=payable_domain,
    # )
    debt_balance = fields.Float(
        compute='_get_debt_balance',
    )
    # debt_balance2 = fields.Float(
    #     related='debt_balance',
    #     string='Balance copy',
    # )

    @api.multi
    # @api.depends('debit', 'credit')
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
        return self.env['account.debt.summary'].search(domain)

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
