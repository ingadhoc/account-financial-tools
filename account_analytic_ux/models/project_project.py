from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    HOURS_PLAN_NAME = "Plan de Horas"
    MATERIALS_PLAN_NAME = "Plan de Materiales"

    use_segmented_analytics = fields.Boolean(
        string="Segmentación Automática de Costos (Horas/Materiales)",
        help="Separa automáticamente los costos del proyecto en cuentas analíticas de Horas y Materiales. "
        "Las partes de horas se imputan al Plan de Horas, los movimientos de inventario al Plan de Materiales.",
    )

    def _ensure_analytic_plan(self, plan_name):
        plan = self.env["account.analytic.plan"].search([("name", "=", plan_name)], limit=1)
        if not plan:
            plan = self.env["account.analytic.plan"].create({"name": plan_name})
        return plan

    def _get_hours_analytic_account(self):
        self.ensure_one()
        plan = self.env["account.analytic.plan"].search([("name", "=", self.HOURS_PLAN_NAME)], limit=1)
        return plan and self[plan._column_name()] or self.env["account.analytic.account"]

    def _get_materials_analytic_account(self):
        self.ensure_one()
        plan = self.env["account.analytic.plan"].search([("name", "=", self.MATERIALS_PLAN_NAME)], limit=1)
        return plan and self[plan._column_name()] or self.env["account.analytic.account"]

    def _get_or_create_analytic_account(self, name, plan):
        account = self.env["account.analytic.account"].search([("name", "=", name), ("plan_id", "=", plan.id)], limit=1)
        if not account:
            account = self.env["account.analytic.account"].create({"name": name, "plan_id": plan.id})
        return account

    def _setup_segmented_analytic_accounts(self):
        hours_plan = self._ensure_analytic_plan(self.HOURS_PLAN_NAME)
        materials_plan = self._ensure_analytic_plan(self.MATERIALS_PLAN_NAME)
        hours_fname = hours_plan._column_name()
        materials_fname = materials_plan._column_name()
        for project in self:
            if not project[hours_fname]:
                project[hours_fname] = self._get_or_create_analytic_account(f"{project.name} - Horas", hours_plan)
            if not project[materials_fname]:
                project[materials_fname] = self._get_or_create_analytic_account(
                    f"{project.name} - Materiales", materials_plan
                )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects.filtered("use_segmented_analytics")._setup_segmented_analytic_accounts()
        return projects

    def _get_segmented_plan_fnames(self):
        """Return (hours_fname, materials_fname) for the segmented plans, or (None, None)."""
        hours_plan = self.env["account.analytic.plan"].search([("name", "=", self.HOURS_PLAN_NAME)], limit=1)
        materials_plan = self.env["account.analytic.plan"].search([("name", "=", self.MATERIALS_PLAN_NAME)], limit=1)
        return (
            hours_plan._column_name() if hours_plan else None,
            materials_plan._column_name() if materials_plan else None,
        )

    @api.onchange("use_segmented_analytics")
    def _onchange_use_segmented_analytics(self):
        if not self.use_segmented_analytics:
            hours_fname, materials_fname = self._get_segmented_plan_fnames()
            if hours_fname:
                self[hours_fname] = False
            if materials_fname:
                self[materials_fname] = False

    def write(self, vals):
        if "use_segmented_analytics" in vals and not vals["use_segmented_analytics"]:
            # Force-clear plan columns in this same write so the form's current values
            # don't restore them via super().write().
            hours_fname, materials_fname = self._get_segmented_plan_fnames()
            if hours_fname:
                vals = dict(vals, **{hours_fname: False})
            if materials_fname:
                vals = dict(vals, **{materials_fname: False})
        res = super().write(vals)
        if vals.get("use_segmented_analytics"):
            self.filtered("use_segmented_analytics")._setup_segmented_analytic_accounts()
        return res
