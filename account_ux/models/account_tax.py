from odoo import api, models
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.constrains("amount_type", "price_include_override", "include_base_amount", "is_base_affected", "amount")
    def _check_company_matches_active_company(self):
        for tax in self:
            has_move_lines = self.env["account.move.line"].sudo().search([("tax_ids", "in", tax.ids)], limit=1)
            if has_move_lines:
                raise ValidationError(
                    "The tax computation fields cannot be modified because there are accounting entries linked to this tax. "
                    "We recommend creating a new tax and archiving this one if necessary."
                )

    def _get_active_equivalent(self):
        """Return these taxes with every archived one swapped for its active twin.

        A twin is the only active tax of the same company, scope, rate and group: that is what an
        archived tax becomes when a company merges or replaces its chart. Archived taxes without a
        single clear twin are dropped, which is the behaviour we had before.
        """
        taxes = self.browse()
        for tax in self:
            if tax.active:
                taxes |= tax
                continue
            equivalent = self.search(
                [
                    ("active", "=", True),
                    ("company_id", "=", tax.company_id.id),
                    ("country_id", "=", tax.country_id.id),
                    ("type_tax_use", "=", tax.type_tax_use),
                    ("tax_scope", "=", tax.tax_scope),
                    ("amount_type", "=", tax.amount_type),
                    ("amount", "=", tax.amount),
                    ("tax_group_id", "=", tax.tax_group_id.id),
                    ("price_include_override", "=", tax.price_include_override),
                ]
            )
            if len(equivalent) == 1:
                taxes |= equivalent
        return taxes
