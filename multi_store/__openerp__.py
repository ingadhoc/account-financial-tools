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
    'name': 'Multi Store',
    'version': '8.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'description': """
Multi Store
===========
The main purpose of this module is to restrict journals access for users on different stores. 

This module add a new concept "stores" in some point similar to multicompany. 
Similar to multicompany:
* User can have multiple stores available (store_ids)
* User can be active only in one store (store_id) which can be set up in his own preferences
* There is a group "multi store" that gives users the availability to see multi store fields

This module also adds a store_id field on journal:
* If store_id = False then journal can be seen by everyone
* If store_id is set, then journal can be seen by users on that store and parent stores

It also restrict edition, creation and unlink on: account.move, account.invoice and account.voucher. 
It is done with the same logic to journal. We do not limitate the "read" of this models because user should need to access those documents, for example, to see partner due.
    """,
    'author':  'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account_voucher',
    ],
    'data': [
        'views/res_store_view.xml',
        'views/res_users_view.xml',
        'views/account_view.xml',
        'security/multi_store_security.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: