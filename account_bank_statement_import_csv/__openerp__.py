# -*- coding: utf-8 -*-
# © 2018 Ivan Todorovich <ivan.todorovich@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'CSV Format Bank Statements Import',
    'version': '9.0.0.0.0',
    'license': 'AGPL-3',
    'author': 'Odoo Community Association (OCA), Ivan Todorovich',
    'website': 'https://github.com/OCA/bank-statement-import',
    'category': 'Banking addons',
    'depends': [
        'account_bank_statement_import',
        'account_bank_statement_import_filename',
    ],
    'data': [
        'views/account_bank_statement_import.xml',
        'views/account_bank_statement_import_csv_wizard.xml',
        'views/account_bank_statement_import_csv_template.xml',
    ],
}
