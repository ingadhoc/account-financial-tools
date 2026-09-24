# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config, float_compare

ALLOW_ROUNDING_EDIT_PARAM = "account_ux.allow_currency_rounding_edit"


class ResCurrency(models.Model):
    _inherit = "res.currency"

    rounding_edit_allowed = fields.Boolean(
        compute="_compute_rounding_edit_allowed",
        help="Technical: whether this database allows editing the rounding factor. Used to show the field"
        " read-only while the system parameter that enables it is disabled.",
    )

    @api.depends_context("uid")
    def _compute_rounding_edit_allowed(self):
        allowed = self._is_rounding_edit_allowed()
        self.rounding_edit_allowed = allowed

    @api.model
    def _seed_rounding_edit_param(self):
        """Crea el parámetro apagado si no está, para que se vea en la lista de
        parámetros del sistema y quien lo necesite sepa que la perilla existe.

        Se llama desde la data del módulo. Es idempotente a propósito: corre en
        cada actualización, no falla si el parámetro ya se creó a mano y no pisa
        el valor de una habilitación deliberada.
        """
        params = self.env["ir.config_parameter"].sudo()
        if not params.get_param(ALLOW_ROUNDING_EDIT_PARAM):
            params.set_param(ALLOW_ROUNDING_EDIT_PARAM, "False")

    def _is_rounding_edit_allowed(self):
        """Indica si se puede modificar el factor de redondeo de una moneda.

        Editar el ``rounding`` a mano (0,001 / 0,0001 en vez de 0,01) rompe los
        cálculos contables aguas abajo, y del relevamiento de la tarea 71732
        salió que ya pasó en 4 bases productivas. El bloqueo se habilita
        explícitamente con el parámetro de sistema
        ``account_ux.allow_currency_rounding_edit``, que nace apagado.

        El bloqueo aplica SOLO en bases productivas de cliente. En cualquier
        otro entorno queda inerte, porque no distingue una edición a mano de
        una escritura por código y hay tests (de Odoo y de terceros) que
        cambian el redondeo de una moneda para armar su escenario.

        Los dos datos se leen sin depender de ningún módulo de la plataforma:
        - ``saas_client.database_uuid``: lo escribe el aprovisionamiento en toda
          base aprovisionada (``saas_provider``). Si no está, no es una base de
          cliente (devcontainer, base armada a mano).
        - opción de configuración ``server_mode`` del servidor: la setea el
          módulo ``server_mode`` y solo queda vacía en las bases de tipo
          Production; Test, Train, Demo, New, Old, etc. traen valor.
        """
        params = self.env["ir.config_parameter"].sudo()
        if not params.get_param("saas_client.database_uuid", False):
            return True
        if config.get("server_mode"):
            return True
        return params.get_param(ALLOW_ROUNDING_EDIT_PARAM, "False").strip().lower() in ("true", "1")

    def write(self, vals):
        # el redondeo que llega con la data de los módulos (instalación o -u) no se bloquea
        if "rounding" in vals and not self.env.context.get("install_mode"):
            new_rounding = vals.get("rounding") or 0.0
            changed = self.filtered(lambda x: float_compare(x.rounding, new_rounding, precision_digits=6))
            if changed and not self._is_rounding_edit_allowed():
                raise UserError(
                    _(
                        "You cannot change the rounding factor of the currency %(currencies)s.\n\n"
                        "Changing it breaks the accounting amounts already computed with the previous"
                        " value. If you really need to change it, contact ADHOC so the system parameter"
                        " '%(param)s' is enabled on this database.",
                        currencies=", ".join(changed.mapped("name")),
                        param=ALLOW_ROUNDING_EDIT_PARAM,
                    )
                )
        return super().write(vals)
