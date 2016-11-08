# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################


import time
from datetime import datetime

from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp import tools
import openerp.addons.decimal_precision as dp

class account_move_line(osv.osv):
    _inherit = "account.move.line"

    def _net(self, cr, uid, ids, field_name, args,context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=None):
            res[line.id] = line.debit - line.credit
        return res

    _columns = {
        # 'net': fields.function(_net, store={'account.move.line': (lambda self, cr, uid, ids, c={}: ids,
                # ['debit', 'credit'],10)}, method=True, string='Net'),     
        # quise hacer la funcion con store pero el problema es que solo me calcula cuando modifico un campo y no me hace el calculo la primer vez
        'net': fields.function(_net, 
            string='Net',
            type='float',
            digits=dp.get_precision(
                                   'Account'),
            ),        
    }
