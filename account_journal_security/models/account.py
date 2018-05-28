##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, SUPERUSER_ID, _
from odoo.exceptions import ValidationError

# agregamos lo auto join para evitar problemas de performance


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    journal_id = fields.Many2one(
        auto_join=True
    )


class AccountMove(models.Model):
    _inherit = 'account.move'

    journal_id = fields.Many2one(
        auto_join=True
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    journal_id = fields.Many2one(
        auto_join=True
    )


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    journal_id = fields.Many2one(
        auto_join=True
    )


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
        ' related to it will be only visible for those users.',
        copy=False
    )

    modification_user_ids = fields.Many2many(
        'res.users',
        'journal_security_journal_modification_users',
        'journal_id',
        'user_id',
        string='Modifications restricted to',
        help='If choose some users, then only this users will be allow to '
        ' create, write or delete accounting data related of this journal. '
        'Information will still be visible for other users.',
        copy=False
    )

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
        # esto es porque las ir rules tienen un cache que no permite
        # que el cambio aplique en el momento
        self.env['ir.rule'].clear_caches()

        if self.modification_user_ids and self.user_ids:
            raise ValidationError(_(
                'No puede setear valores en "Totalmente restricto a:" y '
                '"Modificaciones restrictas a:" simultaneamente. Las opciones '
                'son excluyentes!'))

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

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Para que usuarios los usuarios no puedan elegir diarios donde no puedan
        escribir, modificamos la funcion search. No lo hacemos por regla de
        permiso ya que si no pueden ver los diarios termina dando errores en
        cualquier lugar que se use un campo related a algo del diario
        """
        user = self.env.user
        # if superadmin, do not apply
        if user.id != 1:
            args += [
                '|', ('modification_user_ids', '=', False),
                ('id', 'in', user.modification_journal_ids.ids)]

        return super(AccountJournal, self).search(
            args, offset, limit, order, count=count)
