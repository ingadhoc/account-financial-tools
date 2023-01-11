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
    'name': 'Surcharges on payment terms',
    'version': "15.0.1.0.0",
    'category': 'Accounting',
    'sequence': 14,
    'summary': 'Allow to add surcharges for invoices on payment terms',
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'account_debit_note',
    ],
    'data': [
        'views/account_payment_term_view.xml',
        'views/account_payment_term_surcharge_view.xml',
        'wizard/res_config_settings_views.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml'
    ],
    'installable': True,
    'application': False,
}
