from odoo import api, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    # Forzamos ``account_stock_expense_id`` siempre en False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["account_stock_expense_id"] = False
        return super().create(vals_list)

    def write(self, vals):
        # El plan de cuentas lo setea vía ``write`` diferido, no sólo en el create.
        if "account_stock_expense_id" in vals:
            vals = dict(vals, account_stock_expense_id=False)
        return super().write(vals)
