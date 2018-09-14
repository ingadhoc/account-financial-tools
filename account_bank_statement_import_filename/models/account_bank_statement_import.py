# -*- coding: utf-8 -*-
# © 2018 Ivan Todorovich <ivan.todorovich@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import api, fields, models, _


class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    data_filename = fields.Char('Filename')
