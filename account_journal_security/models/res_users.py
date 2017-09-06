# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, models
# from openerp import SUPERUSER_ID, api, _
# from openerp.exceptions import ValidationError


class Users(models.Model):
    _inherit = 'res.users'

    journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_users',
        'user_id',
        'journal_id',
        'Restricted Journals (TOTAL)',
        # el help ya no es necesario
        # help='This journals and the information related to it will'
        # ' be only visible for users where you specify that they can '
        # 'see them setting this same field.',
        # lo hicimos readonly para hacer que solo se configure desde diarios
        # y no se pueda editar desde usuarios
        readonly=True,
    )

    modification_journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_modification_users',
        'user_id',
        'journal_id',
        'Modification Journals',
        readonly=True,
    )

    # Como lo hicimos readonly la constraint no es mas necesaria
    # @api.multi
    # @api.constrains('journal_ids')
    # def check_restrict_journals(self):
    #     """
    #     Este check parece ser necesario solo por un bug de odoo que no
    #     controlaria los campos m2m
    #     """
    #     # con sudo porque ya no los ve si no se asigno
    #     env_user = self.env.user
    #     if env_user.id == SUPERUSER_ID:
    #         # if superadmin no need to check
    #         return True
    #     for rec in self.sudo():
    #         # if we are editing actual user, continue
    #         if rec == env_user:
    #             continue
    #         for journal in rec.journal_ids:
    #             if env_user not in journal.user_ids:
    #                 raise ValidationError(_(
    #                     'No puede restringir el diario "%s" al usuario "%s" '
    #                     'sin antes restringirlo a usted mismo ya que dejaría'
    #                     ' de verlo.') % (journal.name, rec.name))
