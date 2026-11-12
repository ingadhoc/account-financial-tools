##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import json

from odoo.addons.report_xlsx.controllers.main import ReportController
from odoo.http import request, route
from odoo.http.stream import content_disposition
from odoo.tools.safe_eval import safe_eval, time


class DebtReportController(ReportController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        response = super().report_routes(reportname, docids, converter, **data)
        # the wizard sends the partners in the context, where report_xlsx does not look for the file name
        if converter == "xlsx" and reportname == "account_debt_report.debt_xlsx" and not docids:
            partner_ids = json.loads(data.get("context") or "{}").get("active_ids") or []
            partners = request.env["res.partner"].browse(partner_ids).exists()
            # the sheet groups by commercial partner, so contacts of one company make one sheet
            if len(partners.commercial_partner_id) == 1:
                report = request.env.ref("account_debt_report.account_debt_report")
                filename = "%s.xlsx" % safe_eval(report.print_report_name, {"object": partners[:1], "time": time})
                response.headers["Content-Disposition"] = content_disposition(filename)
        return response
