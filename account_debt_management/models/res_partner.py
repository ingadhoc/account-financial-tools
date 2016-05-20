# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models, fields, _
from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gral_domain = [
        ('reconcile_id', '=', False),
        ('account_id.active', '=', True),
        ('state', '!=', 'draft')]
    receivable_domain = gral_domain + [('account_id.type', '=', 'receivable')]
    payable_domain = gral_domain + [('account_id.type', '=', 'payable')]

    receivable_line_ids = fields.One2many(
        'account.move.line',
        'partner_id',
        domain=receivable_domain,
    )
    payable_line_ids = fields.One2many(
        'account.move.line',
        'partner_id',
        domain=payable_domain,
    )
    debt_balance = fields.Float(
        compute='_get_debt_balance',
    )
    debt_balance2 = fields.Float(
        related='debt_balance',
    )

    @api.one
    @api.depends('debit', 'credit')
    def _get_debt_balance(self):
        self.debt_balance = self.credit - self.debit
