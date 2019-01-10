from odoo import models, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.multi
    def post(self):
        move_lines = self.mapped('line_ids').filtered(
            lambda x: (
                x.account_id.user_type_id.analytic_tag_required and
                x.account_id.analytic_tag_required != 'optional' or
                x.account_id.analytic_tag_required == 'required')
            and not x.analytic_tag_ids)
        if move_lines:
            raise ValidationError(_(
                "Some move lines don't have analytic tags and "
                "analytic tags are required by the account type.\n"
                "* Accounts: %s\n"
                "* Move lines ids: %s" % (
                    ", ".join(move_lines.mapped('account_id.name')),
                    move_lines.ids
                )
            ))
        return super(AccountMove, self).post()
