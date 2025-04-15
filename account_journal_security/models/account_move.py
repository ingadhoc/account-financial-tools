##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models
from odoo.tools import SQL


class AccountMove(models.Model):
    _inherit = "account.move"

    journal_id = fields.Many2one(
        auto_join=True,
    )

    def _compute_has_moves(self):
        query = self.env["res.partner"]._search([("id", "in", self.ids)])
        account_move_query = self.env["account.move"]._search(
            [
                ("company_id", "in", self.env.companies.ids),
                "|",
                ("partner_id", "=", SQL.identifier(query.table, "id")),
                "|",
                ("partner_shipping_id", "=", SQL.identifier(query.table, "id")),
                ("commercial_partner_id", "=", SQL.identifier(query.table, "id")),
            ]
        )
        result = dict(
            self.env.execute_query(
                query.select(
                    "id",
                    SQL(
                        "EXISTS (%s) AS has_moves",
                        account_move_query.subselect(SQL.identifier(account_move_query.table, "id")),
                    ),
                )
            )
        )

        for partner in self:
            partner.has_moves = result.get(partner.id, False)
