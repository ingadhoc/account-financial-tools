from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _timesheet_preprocess_get_accounts(self, vals):
        # picking_entry lines must not get any plan auto-fill: they already have
        # the correct analytic_distribution from stock_move._get_analytic_distribution.
        if vals.get("category") == "picking_entry":
            return {}
        # For segmented projects, route timesheet costs exclusively to the Hours plan.
        # Calling super() would return ALL plan columns (hours + materials), which would
        # inject the materials account on timesheet lines.
        project_id = vals.get("project_id")
        if project_id:
            project = self.env["project.project"].browse(project_id)
            if project.use_segmented_analytics:
                hours_account = project._get_hours_analytic_account()
                account_vals = {}
                if project.account_id:
                    account_vals["account_id"] = project.account_id.id
                if hours_account:
                    account_vals[hours_account.plan_id._column_name()] = hours_account.id
                return account_vals
        return super()._timesheet_preprocess_get_accounts(vals)

    @api.model_create_multi
    def create(self, vals_list):
        # Force non-billable (empty so_line) for every line, timesheet or picking.
        # For stock picking analytic lines also avoid hr_timesheet employee
        # validation by not setting project_id: we only keep the account_id
        # derived from the project. project_id is left set only on timesheets.
        processed = list(vals_list)
        deferred = {}
        for idx, vals in enumerate(vals_list):
            vals = dict(vals, so_line=False)
            if vals.get("category") == "picking_entry" and vals.get("project_id"):
                deferred[idx] = vals["project_id"]
                vals = {k: v for k, v in vals.items() if k != "project_id"}
            processed[idx] = vals

        records = super().create(processed)

        for idx, project_id in deferred.items():
            project = self.env["project.project"].browse(project_id)
            if not records[idx].account_id and project.account_id:
                records[idx].sudo().write({"account_id": project.account_id.id})

        return records

    def _timesheet_postprocess_values(self, values):
        # Segmented-analytics timesheets route costs to the Hours plan. For records
        # that still have no account_id (legacy or edge cases), skip Odoo's
        # "active account required" guard for those records and compute amount directly.
        # picking_entry lines are excluded: their amount comes from the stock move.
        if not any(f in values for f in ("unit_amount", "employee_id", "account_id")):
            return super()._timesheet_postprocess_values(values)

        segmented = self.filtered(
            lambda t: not t.account_id and t.project_id.use_segmented_analytics and t.category != "picking_entry"
        )
        if not segmented:
            return super()._timesheet_postprocess_values(values)

        result = {}
        non_segmented = self - segmented
        if non_segmented:
            result.update(super(AccountAnalyticLine, non_segmented)._timesheet_postprocess_values(values))

        for timesheet in segmented.sudo():
            cost = timesheet._hourly_cost()
            amount = -timesheet.unit_amount * cost
            amount_converted = timesheet.employee_id.currency_id._convert(
                amount, timesheet.currency_id, self.env.company, timesheet.date
            )
            result[timesheet.id] = {"amount": amount_converted}

        return result
