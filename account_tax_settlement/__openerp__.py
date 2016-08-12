# -*- coding: utf-8 -*-
{
    'name': 'Tax Settlement',
    'version': '9.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'description': '''
Tax Settlement
==============
Add a model to manage tax settlements
    ''',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account_move_voucher',
    ],
    'data': [
        'views/account_move_line_view.xml',
        'views/account_journal_view.xml',
        'views/account_tax_settlement_detail_view.xml',
        'views/account_tax_settlement_view.xml',
        'views/account_voucher_view.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': False,
    'auto_install': False,
    'application': False,
}
