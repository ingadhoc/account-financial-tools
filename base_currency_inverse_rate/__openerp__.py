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
    'name': 'Base Currency Inverse Rate',
    'version': '9.0.0.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'summary': '',
    'description': '''
Base Currency Inverse Rate
==========================
In some countries we are use to see exchange rate in the inverse way as odoo
shows it. We show rate FROM base currency and not TO base currency. For eg.
* Base Currency ARS: 1.0
* USD rate: 12.0 (in odoo way 1 / 12.0 = 0.0833)
    ''',
    'depends': [
        'base',
    ],
    'external_dependencies': {
    },
    'data': [
        'views/res_currency_view.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
