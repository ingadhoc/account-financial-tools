##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    reconcile_on_company_currency = fields.Boolean(related="company_id.reconcile_on_company_currency", readonly=False)

    @api.onchange("reconcile_on_company_currency")
    def _onchange_reconcile_on_company_currency(self):
        if (
            self.company_id._origin.reconcile_on_company_currency
            and self.company_id._origin.reconcile_on_company_currency != self.reconcile_on_company_currency
        ):
            return {
                "warning": {
                    "title": _("Warning for %s", self.company_id.name),
                    "message": _(
                        "You are deactivating 'Reconcile on company currency'. "
                        "Future reconciliations will no longer use the company currency, "
                        "which could reintroduce exchange rate differences."
                    ),
                }
            }
