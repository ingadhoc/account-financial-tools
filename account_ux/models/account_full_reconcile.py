# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, models


class AccountFullReconcile(models.Model):
    _inherit = "account.full.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        """With reconcile_on_company_currency, lines sharing a foreign currency can end at zero in that currency
        and still keep a company currency residual worth less than one foreign cent. Odoo only checks the foreign
        residual in that case, so it would mark them fully reconciled and the residual would never be adjusted."""
        vals_list = [vals for vals in vals_list if not self._has_company_currency_residual(vals)]
        return super().create(vals_list)

    @api.model
    def _has_company_currency_residual(self, vals):
        line_ids = [command[1] for command in vals.get("reconciled_line_ids", []) if command[0] == Command.LINK]
        lines = self.env["account.move.line"].browse(line_ids)
        return any(
            line.company_id.reconcile_on_company_currency and not line.company_currency_id.is_zero(line.amount_residual)
            for line in lines
        )
