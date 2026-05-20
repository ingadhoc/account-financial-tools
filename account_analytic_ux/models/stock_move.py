from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_analytic_distribution(self):
        distribution = super()._get_analytic_distribution()
        project = self.picking_id.project_id
        if not project.use_segmented_analytics:
            return distribution
        materials_account = project._get_materials_analytic_account()
        if materials_account:
            distribution = {str(materials_account.id): 100}
        return distribution

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        res = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
        project = self.picking_id.project_id
        # Do NOT set project_id: with a project_id, the profitability report treats the
        # line as a timesheet ("Hours"). Leaving it empty (as standard project_stock_account
        # does) keeps the picking_entry line in the "Materials" section. We only pin the
        # project's main analytic account so it matches that section's domain.
        if project.use_segmented_analytics and project.account_id:
            res["account_id"] = project.account_id.id
        return res
