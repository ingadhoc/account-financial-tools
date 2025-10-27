##############################################################################
#
#    Copyright (C) 2015  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name": "Account UX",
<<<<<<< 4ebd1bfc9c76790d71777f6594ce7697d80617a1
    "version": "19.0.1.1.0",
||||||| 9da79e2a88010fe52e3128c69b4ef48e84e26886
    "version": "18.0.1.21.0",
=======
    "version": "18.0.1.22.0",
>>>>>>> 2454de922bc78f9daa24840e4c30e73cd9e62ab0
    "category": "Accounting",
    "sequence": 14,
    "summary": "",
    "author": "ADHOC SA",
    "website": "www.adhoc.com.ar",
    "license": "AGPL-3",
    "images": [],
    "depends": [
        "account",
        "sale",
        "base_vat",
        "account_debit_note",
    ],
    "data": [
        "security/account_ux_security.xml",
        "security/ir.model.access.csv",
        "wizards/account_change_currency_views.xml",
        "wizards/account_move_change_rate_views.xml",
        "wizards/res_config_settings_views.xml",
        "views/account_account_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_line_views.xml",
        "views/account_reconcile_views.xml",
        "views/res_partner_views.xml",
        "views/account_partial_reconcile_views.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/res_config_settings_views.xml",
        "views/report_payment_receipt_templates.xml",
        "views/account_tax_view.xml",
        "reports/account_invoice_report_view.xml",
    ],
    "demo": [],
    "installable": True,
    # lo hacemos auto install porque este repo no lo podemos agregar en otros
    # por build de travis (ej sipreco) y queremos que para runbot se auto
    # instale
    "auto_install": True,
    "application": False,
    "post_init_hook": "_change_receipt_name",
}
