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
    'name': 'Account UX',
    'version': '12.0.1.0.0',
    'category': 'Accounting',
    'sequence': 14,
    'summary': '',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'account',
        "payment",
        "account_payment_group",
        "web_notify",
    ],
    'data': [
        'security/account_ux_security.xml',
        'wizards/account_change_currency_views.xml',
        'wizards/res_config_settings_views.xml',
        'wizards/account_invoice_tax_wizard_view.xml',
        'views/account_journal_views.xml',
        'views/account_payment_term_views.xml',
        'views/payment_acquirer_views.xml',
        'views/account_invoice_views.xml',
        'views/account_bank_statement_views.xml',
        'views/account_move_line_views.xml',
        'views/account_reconcile_views.xml',
        'views/res_partner_views.xml',
        'views/account_account_type_views.xml',
        'views/account_account_views.xml',
        'views/account_move_views.xml',
        'data/account_payment_method_data.xml',
        'data/mail_data.xml',
        'data/ir_parameters_data.xml',
    ],
    'demo': [
    ],
    'installable': True,
    # lo hacemos auto install porque este repo no lo podemos agregar en otros
    # por build de travis (ej sipreco) y queremos que para runbot se auto
    # instale
    'auto_install': True,
    'application': False,
}
