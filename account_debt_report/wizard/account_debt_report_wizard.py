##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountDebtReportWizard(models.TransientModel):
    _name = "account.debt.report.wizard"
    _description = "Account Debt Report Wizard"

    def _default_result_selection(self):
        return "all" if self.env.user.has_group("account.group_account_invoice") else "receivable"

    company_id = fields.Many2one(
        "res.company", "Company", help="If you don't select a company, debt for all companies will be exported."
    )
    result_selection = fields.Selection(
        [
            ("receivable", "Receivable Accounts"),
            ("payable", "Payable Accounts"),
            ("all", "Receivable and Payable Accounts"),
        ],
        "Account Type's",
        required=True,
        default=_default_result_selection,
    )
    from_date = fields.Date()
    to_date = fields.Date()
    show_invoice_detail = fields.Boolean()
    # TODO implementar
    # show_receipt_detail = fields.Boolean('Show Receipt Detail')
    historical_full = fields.Boolean(
        help="If true, then it will show all partner history. If not, only unreconciled items will be shown."
    )
    company_currency = fields.Boolean(
        default=True,
        help="Includes the items issued in the company currency; the ones issued in other "
        "currencies are left out, not converted. Exchange rate differences follow the "
        "currency they were booked in, so a reconciliation between currencies can leave "
        "one here without the foreign item that generated it. For both reasons this "
        "report may not match the general ledger of the account.\n\n"
        "Checking both options gives the consolidated report: every item, the ones in "
        "foreign currency converted to the company currency along with their original "
        "amount, exchange rate differences included.",
    )
    secondary_currency = fields.Boolean(
        default=True,
        help="Includes only the items issued in a currency other than the company one, "
        "expressed in their own currency. Exchange rate differences booked in the company "
        "currency are left out, as they do not represent debt in this one.\n\n"
        "Checking both options gives the consolidated report: every item, the ones in "
        "foreign currency converted to the company currency along with their original "
        "amount, exchange rate differences included.",
    )

    def confirm(self):
        active_ids = self.env.context.get("active_ids", False)
        if not active_ids:
            return True
        partners = self.env["res.partner"].browse(active_ids)
        data = {
            "secondary_currency": self.secondary_currency,
            "result_selection": self.result_selection,
            "company_id": self.company_id.id,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "historical_full": self.historical_full,
            "show_invoice_detail": self.show_invoice_detail,
        }
        return (
            self.env["ir.actions.report"]
            .search([("report_name", "=", "account_debt_report")], limit=1)
            .with_context(
                company_currency=self.company_currency,
                secondary_currency=self.secondary_currency,
                result_selection=self.result_selection,
                company_id=self.company_id.id,
                from_date=self.from_date,
                to_date=self.to_date,
                historical_full=self.historical_full,
                show_invoice_detail=self.show_invoice_detail,
                # show_receipt_detail=self.show_receipt_detail,
            )
            .report_action(partners, data=data)
        )

    def send_by_email(self):
        active_ids = self.env.context.get("active_ids", [])
        active_id = self.env.context.get("active_id", False)
        partner_ids = active_ids or ([active_id] if active_id else [])
        composition_mode = "comment" if len(partner_ids) == 1 else "mass_mail"
        context = {
            # report keys
            "company_currency": self.company_currency,
            "secondary_currency": self.secondary_currency,
            "result_selection": self.result_selection,
            "company_id": self.company_id.id,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "historical_full": self.historical_full,
            "show_invoice_detail": self.show_invoice_detail,
            # email keys
            "active_ids": active_ids,
            "active_id": active_id,
            "active_model": "res.partner",
            "default_model": "res.partner",
            "default_res_ids": partner_ids,
            "default_composition_mode": composition_mode,
            "default_use_template": True,
            "default_template_id": self.env.ref("account_debt_report.email_template_debt_detail").id,
            "default_partner_to": "{{ object.id or '' }}",
        }
        self = self.with_context(**context)
        return {
            "name": _("Send by Email"),
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "src_model": "res.partner",
            "view_type": "form",
            "context": context,
            "view_mode": "form",
            "target": "new",
            "auto_refresh": 1,
        }

    @api.constrains("company_currency", "secondary_currency")
    def _check_has_one_currency(self):
        for wizard in self:
            if not wizard.company_currency and not wizard.secondary_currency:
                raise ValidationError(_("Debe seleccionar por lo menos una moneda para el informe"))
