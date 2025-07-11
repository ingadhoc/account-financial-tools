from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)

        company = company or self.env.company
        suspense_account = self.env["res.company"].browse(company.id).account_journal_suspense_account_id
        self.env["account.journal"].search(
            [("type", "in", ["bank", "cash"]), ("suspense_account_id", "=", False), ("company_id", "=", company.id)]
        ).write({"suspense_account_id": suspense_account})
