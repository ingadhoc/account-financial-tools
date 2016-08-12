# -*- encoding: utf-8 -*-
{
    'name': 'Account Security Modifications',
    'version': '9.0.1.0.0',
    'description': '''
Account Security Modifications
==============================
It makes the following modifications in security related to accounting:
-----------------------------------------------------------------------
* For group Invoicing & Payments: 
    * Allow to choose journals on invoices
    * Show move and unreconile ammount on vouchers lines 

    ''',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'category': 'Financial',
    'depends': [
        'account_voucher',
    ],
    'data': [
        'invoice_view.xml',
        'voucher_view.xml',
    ],
    'demo_xml': [],
    'active': False,
    'installable': False,
}
