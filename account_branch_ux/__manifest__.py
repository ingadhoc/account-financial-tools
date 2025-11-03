{
    'name': 'Account Branch UX',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Branch management for accounting with abstract mixin',
    'description': """
        This module provides branch management functionality for accounting
        with an abstract mixin that can be inherited by other models.
        
        Features:
        * Branch model with basic information
        * Abstract mixin for branch functionality
        * Security groups and access rights
        * Views for branch management
    """,
    'author': 'ADHOC SA',
    'website': 'https://www.adhoc.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'account',
    ],
    'data': [
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
