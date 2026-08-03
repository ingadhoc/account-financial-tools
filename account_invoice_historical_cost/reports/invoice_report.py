# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.tools import SQL

SALE_MOVE_TYPES = ("out_invoice", "out_receipt", "out_refund")


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    historical_cost = fields.Float(readonly=True)
    historical_cost_provisional = fields.Boolean(readonly=True)
    historical_unit_cost = fields.Float(readonly=True, aggregator="avg")

    _depends = {
        "account.move.line": ["historical_cost", "historical_cost_provisional"],
    }

    def _select(self) -> SQL:
        return SQL(
            """
            %s,
            CASE WHEN move.move_type IN %s
                 THEN line.historical_cost * account_currency_table.rate
                      * (CASE WHEN move.move_type = 'out_refund' THEN 1 ELSE -1 END)
            END AS historical_cost,
            line.historical_cost_provisional AS historical_cost_provisional
            """,
            super()._select(),
            SALE_MOVE_TYPES,
        )

    def _field_to_sql(self, alias: str, field_expr: str, query=None) -> SQL:
        if field_expr == "inventory_value":
            return SQL(
                "COALESCE(%s, %s)",
                self._field_to_sql(alias, "historical_cost", query),
                super()._field_to_sql(alias, field_expr, query),
            )
        if field_expr == "price_margin":
            # base_inventory_sql MUST come from super(), not self.: using
            # self._field_to_sql(alias, "inventory_value", ...) here would
            # coalesce it with historical_cost first, cancelling the delta
            # to 0 always.
            return SQL(
                "%s + COALESCE(%s - %s, 0)",
                super()._field_to_sql(alias, field_expr, query),
                self._field_to_sql(alias, "historical_cost", query),
                super()._field_to_sql(alias, "inventory_value", query),
            )
        if field_expr == "historical_unit_cost":
            return SQL(
                "-%s / NULLIF(%s, 0)",
                self._field_to_sql(alias, "inventory_value", query),
                self._field_to_sql(alias, "quantity", query),
            )
        return super()._field_to_sql(alias, field_expr, query)

    def _read_group_select(self, aggregate_spec: str, query) -> SQL:
        if aggregate_spec != "historical_unit_cost:avg":
            return super()._read_group_select(aggregate_spec, query)
        return SQL(
            "COALESCE(-SUM(%(f_inv)s) / NULLIF(SUM(%(f_qty)s), 0.0), 0)",
            f_qty=self._field_to_sql(self._table, "quantity", query),
            f_inv=self._field_to_sql(self._table, "inventory_value", query),
        )
