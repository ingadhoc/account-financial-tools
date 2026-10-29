from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    bank_id = fields.Many2one("res.bank", string="Bank", index="btree_not_null", tracking=True)
    # One compute per field: with a shared one, setting any of them leaves the others empty
    bank_name = fields.Char(compute="_compute_bank_name", store=True, readonly=False, precompute=True)
    bank_bic = fields.Char(compute="_compute_bank_bic", store=True, readonly=False, precompute=True)

    @api.depends("bank_id.name")
    def _compute_bank_name(self):
        for account in self.filtered("bank_id"):
            account.bank_name = account.bank_id.name

    @api.depends("bank_id.bic")
    def _compute_bank_bic(self):
        for account in self.filtered("bank_id"):
            account.bank_bic = account.bank_id.bic

    def _get_fields_from_bank(self):
        """Fields of the account filled from its bank, emptied when the bank is removed."""
        return ["bank_name", "bank_bic"]

    def write(self, vals):
        # As the related fields of 19.0: removing the bank empties what came from it
        if "bank_id" in vals and not vals["bank_id"]:
            for field in self._get_fields_from_bank():
                vals.setdefault(field, False)
        return super().write(vals)
