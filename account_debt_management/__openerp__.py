# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Account Debt Management',
    'version': '8.0.0.1.0',
    'description': """
Account Debt Management
=======================
It adds new ways to see partner debt:

* Two new tabs (customer debt / supplier debt) on partner form showing the
detail of all unreconciled lines with amount on currencies, financial amount
and cumulative amounts
* New button from partner to display all the history for a partner
* ADd partner balance
""",
    'category': 'Account Reporting',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'account_voucher_payline',
    ],
    'data': [
        # 'wizard/account_summary_wizard_view.xml',
        # 'report/account_summary_report.xml'
        'report/account_debt_summary_view.xml',
        'views/account_move_line_view.xml',
        'views/res_partner_view.xml',
        'views/account_voucher_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
