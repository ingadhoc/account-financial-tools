# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api
# from openerp.exceptions import Warning


class ResCompany(models.Model):

    _inherit = 'res.company'

    short_name = fields.Char(
        help='Short name used to identify this company',
    )

    @api.multi
    def get_company_sufix(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_multi_company'):
            return ' (%s)' % (self.short_name or self.name)
        else:
            return ''
