import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

PARENT_ACCOUNT_HIDDEN_NODES = [
    "//label[@for='reconcile']",  # account_accountant
    "//div[field[@name='reconcile']]",  # account_accountant
    "//group[@name='asset']",  # account_asset
    "//field[@name='fiscal_category_id']",  # account_fiscal_categories
    "//field[@name='l10n_ar_arca_activity_id']",  # l10n_ar
]

JOURNAL_ACCOUNT_FIELDS = [
    "default_account_id",
    "suspense_account_id",
    "non_deductible_account_id",
    "profit_account_id",
    "loss_account_id",
]


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

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        """Hide on parent accounts what other modules add to the form.

        account_ux can't depend on them (some are enterprise), so an XML inheritance would break
        where they are not installed.
        """
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != "form":
            return arch, view
        for xpath in PARENT_ACCOUNT_HIDDEN_NODES:
            for node in arch.xpath(xpath):
                invisible = node.get("invisible")
                node.set("invisible", f"({invisible}) or is_parent_account" if invisible else "is_parent_account")
        return arch, view

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
        journal = (
            self.env["account.journal"]
            .sudo()
            .search(Domain.OR(Domain(field, "in", self.ids) for field in JOURNAL_ACCOUNT_FIELDS), limit=1)
        )
        if journal:
            raise UserError(
                _("You cannot use an account of the journal %(journal)s as parent account.", journal=journal.name)
            )
        repartition_line = (
            self.env["account.tax.repartition.line"].sudo().search([("account_id", "in", self.ids)], limit=1)
        )
        if repartition_line:
            raise UserError(
                _(
                    "You cannot use an account of the tax %(tax)s as parent account.",
                    tax=repartition_line.tax_id.name,
                )
            )
        self.filtered("active").write({"active": False})
