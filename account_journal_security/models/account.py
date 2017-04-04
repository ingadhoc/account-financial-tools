# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api, SUPERUSER_ID, _
from openerp.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    user_ids = fields.Many2many(
        'res.users',
        'journal_security_journal_users',
        'journal_id',
        'user_id',
        # string='Restricted to Users',
        string='Totally restricted to',
        help='If choose some users, then this journal and the information'
        ' related to it will be only visible for those users.')

    modification_user_ids = fields.Many2many(
        'res.users',
        'journal_security_journal_modification_users',
        'journal_id',
        'user_id',
        string='Modifications restricted to',
        help='If choose some users, then only this users will be allow to '
        ' create, write or delete accounting data related of this journal. '
        'Information will still be visible for other users.')

    @api.multi
    @api.constrains('user_ids')
    def check_restrict_users(self):
        self._check_journal_users_restriction('user_ids')

    @api.multi
    @api.constrains('modification_user_ids')
    def check_modification_users(self):
        self._check_journal_users_restriction('modification_user_ids')

    @api.multi
    def _check_journal_users_restriction(self, field):
        """
        Este check parece ser necesario solo por un bug de odoo que no
        controlaria los campos m2m
        """
        # con sudo porque ya no los ve si no se asigno
        env_user = self.env.user
        if env_user.id == SUPERUSER_ID:
            # if superadmin no need to check
            return True
        for rec in self.sudo():
            journal_users = rec[field]
            # journal_users = rec.user_ids
            if journal_users and env_user not in journal_users:
                raise ValidationError(_(
                    'No puede restringir el diario "%s" a usuarios sin '
                    'inclurise a usted mismo ya que dejaria de ver este '
                    'diario') % (rec.name))
        # necesitamos limpiar este cache para que no deje de verlo
        self.env.user.context_get.clear_cache(self)
