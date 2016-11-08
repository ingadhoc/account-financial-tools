# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    short_name = fields.Char(
        help='Short name used to identify this company',
    )

    @api.multi
    def get_company_sufix(self):
        # cuando pedimos para unr registro que no tiene sia no queremos
        # que ensure_one arroje error
        if (
                len(self) != 1 or
                self._context.get('no_company_sufix') or
                not self.env.user.has_group('base.group_multi_company')):
            return ''
        else:
            return ' (%s)' % (self.short_name or self.name)

    consolidation_company = fields.Boolean(
        'Consolidation Company',
    )
