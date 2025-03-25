import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _inherit = "account.account"

    is_monetary = fields.Boolean(
        store=True,
        compute="_compute_is_monetary",
        readonly=False,
    )

    @api.depends("account_type")
    def _compute_is_monetary(self):
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
        for rec in self:
            if rec.account_type in account_types:
                rec.is_monetary = False
            else:
                rec.is_monetary = True
