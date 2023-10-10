from odoo import models


class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    def _load(self, company):
        res = super()._load(company)
        self.env['res.config.settings']._set_default_tax('sale', company.account_sale_tax_id, company)
        self.env['res.config.settings']._set_default_tax('purchase', company.account_purchase_tax_id, company)
        return res
