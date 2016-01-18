# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class product_template(models.Model):
    _inherit = 'product.template'

    standard_price = fields.Float(
        groups='base.group_user,base.group_portal_distributor')
