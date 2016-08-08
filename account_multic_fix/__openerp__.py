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
    'author':  'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'category': 'Accounting & Finance',
    'data': [
        'security/rule.xml',
        'wizard/account_move_line_reconcile_writeoff_view.xml',
        'wizard/account_statement_from_invoice_view.xml',
    ],
    'demo': [],
    'depends': ['account'],
    'description': '''
Account Multi Company Fixes
===========================
1. Filter taxes while loading in invoice for taxes of invoice company
2. Do not allow to change company (we should change taxes and accounts)
3. Filters on moves, statements, etc
''',
    'installable': False,
    'name': 'Account Multi Company Fixes',
    'test': [],
    'version': '8.0.1.4.1'}
