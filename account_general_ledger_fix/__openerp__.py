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
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'category': 'Accounting & Finance',
    'data': [
    ],
    'demo': [],
    'depends': ['account'],
    'description': '''
Account General Ledger Fix
==========================
When getting odoo general ledger with initial balance WITH DATES or PERIODS
and WITHOUT fiscalyear dates, initial balance was not shown, this module
fix that.

IMPORTANI: It wont works with oca webkit financial reports. If you use oca
reports, you can have initial balance if you get report by period or no filter
and account user type close method is not "none".
''',
    'installable': True,
    'name': 'Account General Ledger Fix',
    'test': [],
    'version': '8.0.0.0.0'}
