# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models, modules
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
        """Whether the rounding factor can be changed, set by the system parameter
        ``account_ux.allow_currency_rounding_edit`` (False by default)."""
        params = self.env["ir.config_parameter"].sudo()
        return params.get_param(ALLOW_ROUNDING_EDIT_PARAM, "False").strip().lower() in ("true", "1")

    @api.model
    def _skip_rounding_guard(self):
        # write() cannot tell a manual edit from code, and some tests (Odoo and third party) change
        # the rounding of a currency to build their scenario
        return config["test_enable"] or modules.module.current_test

    def write(self, vals):
        # modules data (install / -u) loads before the registry is ready; unlike install_mode, an RPC call cannot fake it
        if "rounding" in vals and self.env.registry.ready:
            new_rounding = vals.get("rounding") or 0.0
            changed = self.filtered(lambda x: float_compare(x.rounding, new_rounding, precision_digits=6))
            if changed and not self._skip_rounding_guard() and not self._is_rounding_edit_allowed():
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
