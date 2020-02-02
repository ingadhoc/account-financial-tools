{
    "name": "Accounting Documents Management",
    "version": "13.0.1.0.0",
    "author": "Moldeo Interactive,ADHOC SA",
    "license": "AGPL-3",
    "category": "Accounting",
    "depends": [
        "l10n_latam_invoice_document",
    ],
    "data": [
        'view/account_payment_view.xml',
        'view/account_payment_receiptbook_view.xml',
        'data/decimal_precision_data.xml',
        'data/l10n_latam.document.type.csv',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    "demo": [
    ],
    'images': [
    ],
    'installable': True,
}
