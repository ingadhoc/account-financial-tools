from odoo import api, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    # ``account_stock_expense_id`` is always forced to False.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["account_stock_expense_id"] = False
        return super().create(vals_list)

    def write(self, vals):
        # The chart of accounts sets it through a deferred ``write``, not only on create.
        if "account_stock_expense_id" in vals:
            vals = dict(vals, account_stock_expense_id=False)
        return super().write(vals)
