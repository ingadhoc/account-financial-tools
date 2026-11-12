##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountDebtReportXlsx(models.AbstractModel):
    _name = "report.account_debt_report.debt_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Account Debt Report Spreadsheet"

    def get_workbook_options(self):
        # partner names and references are free text: they must never become formulas or links
        return {**super().get_workbook_options(), "strings_to_formulas": False, "strings_to_urls": False}

    def generate_xlsx_report(self, workbook, data, partners):
        self.env["account.debt.report"]._write_xlsx(workbook, partners)
