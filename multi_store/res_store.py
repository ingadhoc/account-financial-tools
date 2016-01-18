# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, SUPERUSER_ID
from openerp.osv import osv


class res_store(models.Model):
    _name = "res.store"
    _description = 'Stores'
    _order = 'parent_id desc, name'

    name = fields.Char('Name', size=128, required=True,)
    parent_id = fields.Many2one('res.store', 'Parent Store', select=True)
    child_ids = fields.One2many('res.store', 'parent_id', 'Child Stores')
    journal_ids = fields.Many2many(
        'account.journal', 'res_store_journal_rel', 'store_id',
        'journal_id', 'Journals')
    company_id = fields.Many2one(
        'res.company', 'Company', required=True,
        default=lambda self: self.env[
            'res.company']._company_default_get('res.store'))
    user_ids = fields.Many2many(
        'res.users', 'res_store_users_rel', 'cid', 'user_id', 'Accepted Users')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The company name must be unique !')
    ]

    _constraints = [
        (osv.osv._check_recursion,
         'Error! You can not create recursive stores.', ['parent_id'])
    ]

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        context = dict(context or {})
        if context.pop('user_preference', None):
            # We browse as superuser. Otherwise, the user would be able to
            # select only the currently visible stores (according to rules,
            # which are probably to allow to see the child stores) even if
            # she belongs to some other stores.
            user = self.pool.get('res.users').browse(cr, SUPERUSER_ID, uid, context=context)
            store_ids = list(set([user.store_id.id] + [cmp.id for cmp in user.store_ids]))
            uid = SUPERUSER_ID
            args = (args or []) + [('id', 'in', store_ids)]
        return super(res_store, self).name_search(cr, uid, name=name, args=args, operator=operator, context=context, limit=limit)