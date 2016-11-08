# -*- coding: utf-8 -*-
{
    'name': 'Account Balance Constraint',
    'version': '9.0.1.0.0',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'description': '''
Account Balance Constraint
==========================
Add fields for min and max balance on accounts.
Add constraint on account.move validation to check account min and max.
    ''',
    'depends': [
        'account'
    ],
    'data': [
        'views/account_view.xml'
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'active': False,
}
