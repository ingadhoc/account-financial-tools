# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
from openerp.exceptions import Warning


class AccountMove(models.Model):
    _inherit = 'account.move'

    name = fields.Char(translate=False)

    @api.one
    @api.constrains('company_id')
    def check_company(self):
        if self.company_id.consolidation_company:
            raise Warning(
                'You can not create entries on a consolidtion company')
