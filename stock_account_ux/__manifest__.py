{
    "name": "Stock Move UX",
    "version": "19.0.1.2.0",
    "category": "Warehouse Management",
    "author": "ADHOC SA",
    "website": "https://www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "Mejoras en la experiencia de usuario para los movimientos de stock",
    "depends": [
        "stock_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_value_views.xml",
        "views/stock_move_views.xml",
        "wizard/stock_move_valuation_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_backend": [
            "stock_account_ux/static/src/**/*",
        ],
        "web.assets_tests": [
            "stock_account_ux/static/tests/**/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
