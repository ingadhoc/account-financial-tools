##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models
from odoo.fields import Domain


class BranchDebtReadMixin(models.AbstractModel):
    """For models whose read rule also accepts the companies of the branch debt
    (``res.users._get_branch_debt_company_ids``), so a document of another branch opens.

    Searches, like the dashboard, the lists and the selectors, keep the scope of the
    native rule, which still applies to write. ``_search`` is left alone on purpose:
    the ORM also uses it to read x2many fields and records already in hand.
    """

    _name = "branch.debt.read.mixin"
    _description = "Readable from the debt of other branches"

    def _branch_debt_search_domain(self, domain):
        if not self.env.su and self.env.user._get_branch_debt_company_ids(self.env.companies.ids):
            return Domain(domain) & Domain(self.env["ir.rule"]._compute_domain(self._name, "write"))
        return domain

    def search_fetch(self, domain, *args, **kwargs):
        return super().search_fetch(self._branch_debt_search_domain(domain), *args, **kwargs)

    def search_count(self, domain, *args, **kwargs):
        return super().search_count(self._branch_debt_search_domain(domain), *args, **kwargs)

    def _read_group(self, domain, *args, **kwargs):
        return super()._read_group(self._branch_debt_search_domain(domain), *args, **kwargs)
