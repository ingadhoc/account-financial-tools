# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, fields, models


class account_summary_wizard(models.TransientModel):
    _name = 'account_summary_wizard'
    _description = 'Partner Account Summary Wizard'

    from_date = fields.Date('From')
    to_date = fields.Date('To')
    company_id = fields.Many2one(
        'res.company',
        help="If blank are to list all movements for which the user has "
        "permission , if a company is defined will be shown only movements "
        "that company")
    show_invoice_detail = fields.Boolean('Show Invoice Detail')
    show_receipt_detail = fields.Boolean('Show Receipt Detail')
    result_selection = fields.Selection(
        [('customer', 'Receivable Accounts'),
         ('supplier', 'Payable Accounts'),
         ('customer_supplier', 'Receivable and Payable Accounts')],
        "Account Type's", required=True, default='customer_supplier')

    @api.multi
    def account_summary(self):
        active_id = self._context.get('active_id', False)
        active_ids = self._context.get('active_ids', False)
        if not active_ids:
            active_ids = [self.env.user.partner_id]
        if not active_id:
            partner = self.env.user.partner_id
            active_id = partner.id
        else:
            partner = self.env['res.partner'].browse(active_id)
        if self.result_selection == 'customer':
            account_types = ['receivable']
        elif self.result_selection == 'supplier':
            account_types = ['payable']
        else:
            account_types = ['payable', 'receivable']
        return self.env['report'].with_context(
            from_date=self.from_date,
            to_date=self.to_date,
            company_id=self.company_id.id,
            active_id=active_id,
            active_ids=active_ids,
            show_invoice_detail=self.show_invoice_detail,
            show_receipt_detail=self.show_receipt_detail,
            account_types=account_types).get_action(
            partner.commercial_partner_id, 'report_account_summary')
