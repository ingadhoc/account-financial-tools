{
    "name": "Stock Move UX",
    "version": "19.0.1.1.0",
    "category": "Warehouse Management",
    "author": "ADHOC SA",
    "website": "https://www.adhoc.com.ar",
    "license": "AGPL-3",
    "summary": "Mejoras en la experiencia de usuario para los movimientos de stock",
    "depends": [
        "stock_account",
    ],
    "data": [
        "views/stock_move_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": True,
    "application": False,
}
