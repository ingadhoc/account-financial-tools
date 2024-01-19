{
    'name': 'Account Followup Trafficlight',
    'version': "15.0.1.0.0",
    'category': 'Accounting',
    'sequence': 14,
    'summary': 'Calculate semaphore through debt for selected partners',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'account_followup',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': False,
}
