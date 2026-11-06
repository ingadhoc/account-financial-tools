##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, tools


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_branch_debt_company_ids(self, company_ids):
        """Companies whose debt the user may read besides the ones they work in.

        Used from the read rules on journal entries and on every search of the models of
        ``branch.debt.read.mixin``. ``company_ids`` comes from the rule evaluation context,
        because ``user`` is evaluated there with an empty context and its ``env.companies``
        is not the selection of the company switcher.
        """
        return list(self._get_branch_debt_company_ids_cached(tuple(sorted(company_ids))))

    # Same cache as has_group (_get_group_ids), plus res.company.cache_invalidation_fields and company create.
    @tools.ormcache("self.id", "company_ids")
    def _get_branch_debt_company_ids_cached(self, company_ids):
        if not self.has_group("account_ux.group_read_branch_debt"):
            return ()
        companies = self.env["res.company"]
        for company in self.env["res.company"].sudo().browse(company_ids):
            companies |= company._get_branch_debt_companies()
        return tuple(companies.ids)
