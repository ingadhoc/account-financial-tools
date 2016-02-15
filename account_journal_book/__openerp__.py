# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2009 Zikzakmedia S.L. (http://zikzakmedia.com)
#                       Jordi Esteve <jesteve@zikzakmedia.com>
#    Copyright (c) 2013 Joaquin Gutierrez (http://www.gutierrezweb.es)
#    Copyright (c) 2015 Serv. Tecnol. Avanzados - Pedro M. Baeza
#    Copyright (c) 2015 ADHOC SA - Juan Jose Scarafia
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': "Libro Diario Contable",
    'version': "8.0.0.3.1",
    'author': "Spanish Localization Team,"
              "Zikzakmedia SL,"
              "J. Gutierrez,"
              "Serv. Tecnol. Avanzados,"
              "Odoo Community Association (OCA),"
              "ADHOC SA",
    'website': "www.adhoc.com.ar",
    'category': "Localisation/Accounting",
    'license': "AGPL-3",
    'depends': [
        "account",
    ],
    'data': [
        "wizard/wizard_print_journal_entries_view.xml",
        # 'wizard/account_period_close_wizard_view.xml',
        'wizard/account_move_book_renumber_wizard_view.xml',
        "report/account_journal_book.xml",
        'views/account_view.xml',
        'data/sequence.xml',
    ],
    "installable": True,
}
