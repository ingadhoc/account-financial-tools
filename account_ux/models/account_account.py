import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _name = "account.account"
    _inherit = ["account.account", "branch.debt.read.mixin"]

    is_monetary = fields.Boolean(
        store=True,
        compute="_compute_is_monetary",
        readonly=False,
    )
    child_ids = fields.One2many("account.account", "parent_id", string="Child Accounts", context={"active_test": False})
    is_parent_account = fields.Boolean(compute="_compute_is_parent_account", store=True)

    @api.depends("child_ids")
    def _compute_is_parent_account(self):
        for rec in self:
            rec.is_parent_account = bool(rec.child_ids)

    @api.depends("account_type")
    def _compute_is_monetary(self):
        """Set is_monetary in False to the corresponding accounts taking into account the account type"""
        account_types = [
            "asset_non_current",
            "asset_fixed",
            "liability_non_current",
            "equity",
            "equity_unaffected",
            "equity_retained",
            "income",
            "income_other",
            "expense",
            "expense_other",
            "expense_depreciation",
            "expense_direct_cost",
            "off_balance",
        ]
        for rec in self:
            if rec.account_type in account_types:
                rec.is_monetary = False
            else:
                rec.is_monetary = True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.parent_id._set_as_parent_account()
        return records

    def write(self, vals):
        if vals.get("active") and self.with_context(active_test=False).search_count(
            [("parent_id", "in", self.ids)], limit=1
        ):
            raise UserError(_("You cannot unarchive an account that has child accounts."))
        res = super().write(vals)
        if vals.get("parent_id"):
            self.parent_id._set_as_parent_account()
        return res

    def _set_as_parent_account(self):
        """Parent accounts only group other accounts, so they are kept archived like the core charts do."""
        if self.env["account.move.line"].sudo().search_count([("account_id", "in", self.ids)], limit=1):
            raise UserError(_("You cannot use an account with journal items as parent account."))
        self.filtered("active").write({"active": False})
