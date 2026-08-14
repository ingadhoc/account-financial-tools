##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("vat")
    def _check_company_legal_entity_chain(self):
        """Revalidate the branch chain when a company's Tax ID changes.

        ``res.company.vat`` is a non-stored related field on the partner, so
        ``@api.constrains`` cannot watch it from the company side — it only fires on
        stored fields. The write always lands here, whether it came from the company
        form or from the partner form, so this is the one place that catches it.
        """
        companies = self.env["res.company"].sudo().search([("partner_id", "in", self.ids)])
        companies._check_legal_entity_vat_chain()
