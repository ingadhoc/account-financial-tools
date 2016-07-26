# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, fields, models


class account_debt_report_wizard(models.TransientModel):
    _name = 'account.debt.report.wizard'
    _description = 'Account Debt Report Wizard'

    company_id = fields.Many2one(
        'res.company',
        'Company',
        help="If you don't select a company, debt for all companies will be "
        "exported."
    )
    company_type = fields.Selection([
        ('group_by_company', 'Group by Company'),
        ('consolidate', 'Consolidate all Companies'),
    ],
        default='group_by_company',
    )
    result_selection = fields.Selection(
        [('receivable', 'Receivable Accounts'),
         ('payable', 'Payable Accounts'),
         ('all', 'Receivable and Payable Accounts')],
        "Account Type's",
        required=True,
        default='all'
    )
    from_date = fields.Date('From')
    to_date = fields.Date('To')
    show_invoice_detail = fields.Boolean('Show Invoice Detail')
    show_receipt_detail = fields.Boolean('Show Receipt Detail')
    # TODO ver si implementamos esta opcion imprimiendo subilistado de o2m
    group_by_move = fields.Boolean(
        'Group By Move',
        default=True)
    # secondary_currency_id = fields.Many2one(
    secondary_currency = fields.Boolean(
        # 'res.currency',
        'Secondary Currency',
        help='Add columns for secondary currency?')

    @api.multi
    def confirm(self):
        # active_id = self._context.get('active_id', False)
        active_ids = self._context.get('active_ids', False)
        if not active_ids:
            return True
            # active_ids = [self.env.user.partner_id]
        partners = self.env['res.partner'].browse(active_ids)
        # if not active_id:
        #     partner = self.env.user.partner_id
        #     active_id = partner.id
        # else:
        #     partner = self.env['res.partner'].browse(active_id)
        # if self.result_selection == 'customer':
        #     account_types = ['receivable']
        # elif self.result_selection == 'supplier':
        #     account_types = ['payable']
        # else:
        #     account_types = ['payable', 'receivable']
        return self.env['report'].with_context(
            # group_by_move=self.group_by_move,
            # secondary_currency=self.secondary_currency,
            # # secondary_currency_id=self.secondary_currency_id.id,
            result_selection=self.result_selection,
            company_type=self.company_type,
            company_id=self.company_id.id,
            from_date=self.from_date,
            # to_date=self.to_date,
            # company_id=self.company_id.id,
            # active_id=active_id,
            # active_ids=active_ids,
            # show_invoice_detail=self.show_invoice_detail,
            # show_receipt_detail=self.show_receipt_detail,
            # account_types=account_types
        ).get_action(
            partners, 'account_debt_report')
