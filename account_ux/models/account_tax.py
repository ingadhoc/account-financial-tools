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
