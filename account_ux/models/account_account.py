import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_monetary = fields.Boolean(default=True)

    @api.model
    def set_non_monetary(self, company):
        """Set is_monetary in False to the corresponding accounts taking into account the account type"""
        account_types = [
            "asset_non_current",
            "asset_fixed",
            "liability_non_current",
            "equity",
            "equity_unaffected",
            "income",
            "income_other",
            "expense",
            "expense_depreciation",
            "expense_direct_cost",
            "off_balance",
        ]
        if accounts := self.search(
            [("account_type", "in", account_types), *self.env["account.account"]._check_company_domain(company)]
        ).filtered(lambda x: x.company_fiscal_country_code == "AR"):
            accounts.write({"is_monetary": False})
            _logger.info("Is Monetary is False on %s accounts ." % (company.name))
