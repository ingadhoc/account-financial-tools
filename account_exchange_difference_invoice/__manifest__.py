{
    "name": "Account Exchange Difference Invoice",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "website": "www.adhoc.com.ar",
    "author": "ADHOC SA",
    "license": "AGPL-3",
    "depends": [
        "account_debit_note",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_line_views.xml",
        "wizards/exchange_difference_wizard_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "demo": [
        "demo/demo_data.xml",
    ],
}
