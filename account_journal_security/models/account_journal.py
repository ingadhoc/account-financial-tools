##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import SQL


class AccountJournal(models.Model):
    _inherit = "account.journal"

    user_ids = fields.Many2many(
        "res.users",
        "journal_security_journal_users",
        "journal_id",
        "user_id",
        # string='Restricted to Users',
        string="Totally allowed to",
        help="If choose some users, then this journal and the information"
        " related to it will be only visible for those users.",
        copy=False,
        context={"active_test": False},
    )

    modification_user_ids = fields.Many2many(
        "res.users",
        "journal_security_journal_modification_users",
        "journal_id",
        "user_id",
        string="Modifications allowed to",
        help="If choose some users, then only this users will be allow to "
        " create, write or delete accounting data related of this journal. "
        "Information will still be visible for other users.",
        copy=False,
        context={"active_test": False},
    )

    journal_restriction = fields.Selection(
        [("none", "Ninguna"), ("modification", "Modificacion"), ("total", "Total")],
        string="Tipo de Restriccion",
        compute="_compute_journal_restriction",
        readonly=False,
    )

    @api.depends()
    def _compute_journal_restriction(self):
        for rec in self:
            if rec.user_ids:
                rec.journal_restriction = "total"
            elif rec.modification_user_ids:
                rec.journal_restriction = "modification"
            else:
                rec.journal_restriction = "none"

    @api.constrains("user_ids")
    def check_restrict_users(self):
        self._check_journal_users_restriction("user_ids")

    @api.constrains("modification_user_ids")
    def check_modification_users(self):
        self._check_journal_users_restriction("modification_user_ids")

    def _check_journal_users_restriction(self, field):
        """
        Este check parece ser necesario solo por un bug de odoo que no
        controlaria los campos m2m
        """
        # esto es porque las ir rules tienen un cache que no permite
        # que el cambio aplique en el momento
        self.env.flush_all()
        self.env.registry.clear_cache()

        # FIXME: Con el onchange de journal_restriction esto
        # ya no debería ocurrir.
        if self.modification_user_ids and self.user_ids:
            raise ValidationError(
                _(
                    'No puede setear valores en "Totalmente restricto a:" y '
                    '"Modificaciones restrictas a:" simultaneamente. Las opciones '
                    "son excluyentes!"
                )
            )

        # con sudo porque ya no los ve si no se asigno
        env_user = self.env.user
        if env_user.id == SUPERUSER_ID:
            # if superadmin no need to check
            return True
        for rec in self.sudo():
            journal_users = rec[field]
            # journal_users = rec.user_ids
            if journal_users and env_user not in journal_users:
                raise ValidationError(
                    _(
                        'No puede restringir el diario "%s" a usuarios sin '
                        "inclurise a usted mismo ya que dejaria de ver este "
                        "diario"
                    )
                    % (rec.name)
                )
        # necesitamos limpiar este cache para que no deje de verlo
        self.env.flush_all()
        self.env.registry.clear_cache()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """
        Para que usuarios los usuarios no puedan elegir diarios donde no puedan
        escribir, modificamos la funcion search. No lo hacemos por regla de
        permiso ya que si no pueden ver los diarios termina dando errores en
        cualquier lugar que se use un campo related a algo del diario
        """
        # Ensure domain is a Domain object
        domain = Domain(domain)
        user = self.env.user
        # Agregamos el with_user ya que por alguna razon llega con sudo y nos da un falso positivo indicando
        # que el usuario es super usuario. De esta forma nos aseguramos verdaderamente si lo es.
        self.env.cr.execute(
            """
                SELECT journal_id
                FROM journal_security_journal_modification_users
                WHERE user_id != %s
            """,
            (user.id,),
        )
        modification_journal_ids = [r[0] for r in self.env.cr.fetchall()]
        self.env.cr.execute(
            """
                SELECT journal_id
                FROM journal_security_journal_users
                WHERE user_id != %s
            """,
            (user.id,),
        )
        self.env.cr.execute(
            """
                SELECT journal_id
                FROM journal_security_journal_users
                WHERE user_id = %s
            """,
            (user.id,),
        )
        user_journal_ids = [r[0] for r in self.env.cr.fetchall()]
        restric_user_journal_ids = [r[0] for r in self.env.cr.fetchall()]
        journal_ids = restric_user_journal_ids + modification_journal_ids
        if not self.with_user(user.id).env.is_superuser() and not self.env.context.get("journal_security", False):
            domain += ["|", ("user_ids", "=", False), ("id", "in", user_journal_ids)]
        if not self.with_user(user.id).env.is_superuser() and self.env.context.get("journal_security", False):
            domain += ["|", ("modification_user_ids", "=", False), ("id", "not in", journal_ids)]
        if limit == 1 and not self.with_user(user.id).env.is_superuser():
            # Agregamos el domain de los journals donde el usuario tiene permisos
            domain += [
                "|",
                "&",
                ("user_ids", "=", False),
                ("modification_user_ids", "=", False),
                ("id", "not in", journal_ids),
            ]
        return super()._search(domain, offset, limit, order, **kwargs)

    @api.onchange("journal_restriction")
    def unset_modification_user_ids(self):
        """
        Al cambiar una opción por otra, limpiar el campo M2M
        que se oculta para evitar conflictos al guardar.
        """
        if self.journal_restriction == "modification":
            self.modification_user_ids = self.user_ids
            self.user_ids = None
        elif self.journal_restriction == "total":
            self.user_ids = self.modification_user_ids
            self.modification_user_ids = None
        else:
            # Es necesario que se limpien ambos campos cuando se seleccione
            # "Ninguna", sino no se guardan los cambios.
            self.user_ids = None
            self.modification_user_ids = None

    def _get_to_check_payment_query(self):
        query, selects = super()._get_to_check_payment_query()
        new_selects = []
        for select in selects:
            if select.code in ("company_id"):
                new_selects.append(SQL.identifier(query.table, select.code))
            elif select.code in ("currency_id AS currency"):
                new_selects.append(SQL("%s AS currency" % SQL.identifier(query.table, "currency_id").code))
            else:
                new_selects.append(select)
        return query, new_selects
