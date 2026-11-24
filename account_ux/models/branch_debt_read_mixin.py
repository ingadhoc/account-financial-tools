##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models
from odoo.addons.base.models.ir_access import IN_SELECTION
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

# The read accesses of security/account_ux_security.xml that add the branch debt.
BRANCH_DEBT_ACCESSES = (
    "account_ux.account_journal_read_rule",
    "account_ux.account_move_read_rule",
    "account_ux.account_move_line_read_rule",
    "account_ux.account_account_read_rule",
    "account_ux.account_tax_read_rule",
    "account_ux.account_tax_group_read_rule",
    "account_ux.account_tax_repartition_line_read_rule",
    "account_ux.account_payment_term_read_rule",
    "account_ux.res_company_branch_debt_read_rule",
)


class BranchDebtReadMixin(models.AbstractModel):
    """For models whose read rule also accepts the companies of the branch debt
    (``res.users._get_branch_debt_company_ids``), so a document of another branch opens.

    Searches, like the dashboard, the lists and the selectors, keep the scope of the
    native rule, which still applies to write. ``_search`` is left alone on purpose:
    the ORM also uses it to read x2many fields and records already in hand.
    """

    _name = "branch.debt.read.mixin"
    _description = "Readable from the debt of other branches"

    def _branch_debt_native_domain(self):
        """The native scope of this model for the current user: the read permissions of
        their groups, without the ones that add the branch debt, and the restrictions
        (accesses without a group) for update, the ones that lost read to the accesses
        of this module. Not ``_access_domain("write")``: it is false for a user who can
        only read."""
        IrAccess = self.env["ir.access"]
        branch_debt_access_ids = {
            self.env["ir.model.data"]._xmlid_to_res_id(xml_id, raise_if_not_found=False)
            for xml_id in BRANCH_DEBT_ACCESSES
        }
        group_ids = set(self.env.user._get_group_ids())
        eval_context = None
        permissions = []
        restrictions = []
        for access in IrAccess._get_all_access().get(self._name, ()):
            if access.id in branch_debt_access_ids:
                continue
            if access.group_id:
                if access.group_id not in group_ids or access.operation not in IN_SELECTION["read"]:
                    continue
            elif access.operation not in IN_SELECTION["write"]:
                continue
            domain = access.domain
            if not isinstance(domain, Domain):
                if eval_context is None:
                    eval_context = IrAccess._eval_context()
                domain = Domain(safe_eval(domain, eval_context))
            (permissions if access.group_id else restrictions).append(domain)
        return Domain.OR(permissions) & Domain.AND(restrictions)

    def _branch_debt_search_domain(self, domain):
        if not self.env.su and self.env.user._get_branch_debt_company_ids(self.env.companies.ids):
            return Domain(domain) & self._branch_debt_native_domain()
        return domain

    @api.model
    def search_fetch(self, domain, *args, **kwargs):
        return super().search_fetch(self._branch_debt_search_domain(domain), *args, **kwargs)

    @api.model
    def search_count(self, domain, *args, **kwargs):
        return super().search_count(self._branch_debt_search_domain(domain), *args, **kwargs)

    @api.model
    def _read_group(self, domain, *args, **kwargs):
        return super()._read_group(self._branch_debt_search_domain(domain), *args, **kwargs)
