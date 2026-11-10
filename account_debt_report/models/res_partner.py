##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_open_debt_report_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.debt.report.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("account_debt_report.account_debt_report_wizard_form").id,
            "target": "new",
            "context": {
                "partner_id": self.id,
            },
        }
