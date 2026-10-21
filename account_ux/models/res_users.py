##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_branch_debt_company_ids(self, company_ids):
        """Companies whose debt the user may read besides the ones they work in.

        Used from the read rules on journal entries. ``company_ids`` comes from the rule
        evaluation context, because ``user`` is evaluated there with an empty context and
        its ``env.companies`` is not the selection of the company switcher.
        """
        companies = self.env["res.company"]
        for company in self.env["res.company"].sudo().browse(company_ids):
            companies |= company._get_branch_debt_companies()
        return companies.ids
