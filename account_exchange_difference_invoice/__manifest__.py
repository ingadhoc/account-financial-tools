{
    "name": "Account Exchange Difference Invoice",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "website": "www.adhoc.com.ar",
    "author": "ADHOC SA",
    "license": "AGPL-3",
    "depends": [
        "account_debit_note",
        "account_payment_pro",  # es para data demo con counterpart currency y demás, estrictamente no es necesario
        "l10n_ar_tax",  # ex por data demo (y la realidad es el único país que usa esta funcionalidad por ahora)
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_line_views.xml",
        "wizards/exchange_difference_wizard_views.xml",
        "views/res_config_settings.xml",
    ],
    "demo": [
        "demo/account_exchange_demo.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
