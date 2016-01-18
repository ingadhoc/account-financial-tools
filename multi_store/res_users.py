# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class res_users(models.Model):
    _inherit = 'res.users'

    store_id = fields.Many2one(
        'res.store', 'Store', context={'user_preference': True},
        help='The store this user is currently working for.')
    store_ids = fields.Many2many(
        'res.store', 'res_store_users_rel', 'user_id', 'cid', 'Stores')

    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights on
        store fields. Access rights are disabled by
        default, but allowed on some specific fields defined in
        self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        init_res = super(res_users, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        self.SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
        self.SELF_WRITEABLE_FIELDS.append('store_id')
        # duplicate list to avoid modifying the original reference
        self.SELF_READABLE_FIELDS = list(self.SELF_READABLE_FIELDS)
        self.SELF_READABLE_FIELDS.append('store_id')
        return init_res
