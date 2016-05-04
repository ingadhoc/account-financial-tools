# -*- coding: utf-8 -*-
{
    'name': 'Tax Settlement - Voucher Withholding Integration',
    'version': '8.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'description': """
Tax Settlement - Voucher Withholding Integration
================================================
    """,
    'author':  'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account_tax_settlement',
        'account_voucher_withholding',
    ],
    'data': [
        'views/account_voucher_withholding_view.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': False,
    'auto_install': True,
    'application': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
