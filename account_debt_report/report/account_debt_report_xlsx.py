##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountDebtReportXlsx(models.AbstractModel):
    _name = "report.account_debt_report.debt_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Account Debt Report Spreadsheet"

    def generate_xlsx_report(self, workbook, data, partners):
        self.env["account.debt.report"]._write_xlsx(workbook, partners)
