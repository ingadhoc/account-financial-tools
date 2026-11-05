import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

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

    parent_id = fields.Many2one(context={"active_test": False, "show_parent_accounts": True})
    child_ids = fields.One2many("account.account", "parent_id", context={"active_test": False})
    is_parent_account = fields.Boolean(compute="_compute_is_parent_account", store=True)

    @api.depends("child_ids")
    def _compute_is_parent_account(self):
        for rec in self:
            rec.is_parent_account = bool(rec.child_ids)

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        # Parent accounts only group other accounts, so they are not offered where an account is used
        if not self.env.context.get("show_parent_accounts"):
            domain = Domain(domain or []) & Domain("is_parent_account", "=", False)
        return super().name_search(name, domain, operator, limit)

    @api.constrains("parent_id")
    def _check_parent_without_journal_items(self):
        if self.parent_id and self.env["account.move.line"].sudo().search_count(
            [("account_id", "in", self.parent_id.ids)], limit=1
        ):
            raise ValidationError(_("You cannot use an account with journal items as parent account."))

    def write(self, vals):
        if "active" in vals and not vals["active"]:
            self.child_ids.write({"parent_id": False})
        return super().write(vals)
