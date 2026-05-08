##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.misc import unquote
from odoo.tools.safe_eval import safe_eval


class AccountJournal(models.Model):
    _inherit = "account.journal"
    _order = "branch_order,sequence, type, code"

    mail_template_id = fields.Many2one(
        "mail.template",
        "Email Template",
        domain=[("model", "=", "account.move")],
        help="If set an email will be sent to the customer after the invoices"
        " related to this journal has been validated.",
    )
    shared_to_branches = fields.Boolean(
        compute="_compute_shared_to_branches",
        store=True,
        readonly=False,
        help="If enabled, this journal will be available for use in child "
        "companies (branches). This allows subsidiaries to use the parent "
        "company's journals for their transactions.",
    )
    has_child_companies = fields.Boolean(compute="_compute_has_child_companies")
    branch_order = fields.Integer(
        compute="_compute_branch_order",
        store=True,
        help="Priority sequence for branches. Low number if I am a branch, high number if I am a parent",
    )

    @api.depends("company_id", "company_id.child_ids")
    def _compute_has_child_companies(self):
        for journal in self:
            journal.has_child_companies = bool(journal.company_id.child_ids)

    @api.depends("company_id", "company_id.child_ids", "company_id.parent_id")
    def _compute_branch_order(self):
        for journal in self:
            # Calculate the leves of the child hierarchy
            level = 0
            companies_to_check = journal.company_id.child_ids
            while companies_to_check:
                level += 10
                # Get all children of the next level
                companies_to_check = companies_to_check.mapped("child_ids")

            if journal.company_id.child_ids:
                # If it has children, the base value is 100 plus level
                journal.branch_order = 100 + level
            elif journal.company_id.parent_id:
                # If it's a branch (has a parent), low value
                journal.branch_order = 100
            else:
                # If it has neither parent nor children, base value
                journal.branch_order = 10

    @api.onchange("shared_to_branches")
    def _onchange_shared_to_branches(self):
        if self.type == "sale" and self.shared_to_branches:
            return {
                "warning": {
                    "title": _("Warning!"),
                    "message": _("No se recomiendan compartir a sucursales los diarios de tipo 'Venta'."),
                }
            }

    @api.depends("type")
    def _compute_shared_to_branches(self):
        shared = self.filtered(lambda j: j.type in ["general", "purchase"])
        shared.shared_to_branches = True
        (self - shared).shared_to_branches = False

        # In case of test environment (but not demo data loading), share all journals to branches
        if tools.config["test_enable"] and not self.env.context.get("demo"):
            self.shared_to_branches = True

    def _check_company_domain(self, companies) -> Domain:
        """TODO"""
        if isinstance(companies, unquote):
            companies = unquote(f"{companies}")
        else:
            companies = models.to_record_ids(companies)
        domain = Domain("company_id", "in", companies) | Domain(
            [("company_id", "parent_of", companies), ("shared_to_branches", "=", True)]
        )
        return domain

    @api.depends("type")
    def _compute_payment_sequence(self):
        # Por defecto lo ponemos en False para evitar errores en la secuencia
        super()._compute_payment_sequence()
        for journal in self:
            journal.payment_sequence = False

    @api.model
    def _fill_missing_values(self, vals, protected_codes=False):
        journal_type = vals.get("type")
        company = self.env["res.company"].browse(vals["company_id"]) if vals.get("company_id") else self.env.company
        if journal_type == "credit":
            if not vals.get("default_account_id"):
                default_account_id = self._create_default_account(company, journal_type, vals)
                vals["default_account_id"] = default_account_id
        super()._fill_missing_values(vals, protected_codes=protected_codes)

    def open_invalid_statements_action(self):
        self.ensure_one()
        res = super().open_invalid_statements_action()
        res["domain"] = str(safe_eval(res["domain"]) + [("journal_id", "=", self.id)])
        return res

    def write(self, vals):
        if vals.get("default_account_id"):
            new_account = self.env["account.account"].browse(vals["default_account_id"])
            for journal in self.filtered(lambda j: j.has_entries and j.default_account_id):
                if new_account.account_type != journal.default_account_id.account_type:
                    raise ValidationError(
                        _(
                            "Cannot change the account type of the default account on journal '%(journal)s' "
                            "because it already has accounting entries. "
                            "Current type: '%(old_type)s', new type: '%(new_type)s'.",
                            journal=journal.display_name,
                            old_type=journal.default_account_id.account_type,
                            new_type=new_account.account_type,
                        )
                    )
        return super().write(vals)
