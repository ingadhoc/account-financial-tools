# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.models import TableSQL
from odoo.tools import SQL

SALE_MOVE_TYPES = ("out_invoice", "out_receipt", "out_refund")


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    historical_cost = fields.Monetary(
        readonly=True,
        currency_field="company_currency_id",
        aggregator="sum_currency",
    )
    historical_cost_provisional = fields.Boolean(readonly=True)
    historical_cost_frozen = fields.Boolean(readonly=True)
    historical_unit_cost = fields.Monetary(
        readonly=True,
        currency_field="company_currency_id",
        aggregator="avg_currency",
    )

    _depends = {
        "account.move.line": ["historical_cost", "historical_cost_provisional"],
    }

    def _select_list(self, table: TableSQL):
        select_list = super()._select_list(table)
        # inventory_value and price_margin are replaced in place, reusing the
        # core expression as the fallback for lines without a frozen cost.
        base_inventory_value = self._get_select_expr(select_list, "inventory_value")
        base_price_margin = self._get_select_expr(select_list, "price_margin")
        quantity = self._get_select_expr(select_list, "quantity")
        historical_cost = SQL(
            "CASE WHEN %s IN %s THEN %s * (CASE WHEN %s = 'out_refund' THEN 1 ELSE -1 END) END",
            table.move_type,
            SALE_MOVE_TYPES,
            table.historical_cost,
            table.move_type,
        )
        inventory_value = SQL("COALESCE(%s, %s)", historical_cost, base_inventory_value)
        self._replace_select_expr(select_list, "inventory_value", inventory_value)
        self._replace_select_expr(
            select_list,
            "price_margin",
            SQL("%s + COALESCE(%s - %s, 0)", base_price_margin, historical_cost, base_inventory_value),
        )
        return select_list + [
            SQL("%s AS historical_cost", historical_cost),
            SQL("%s AS historical_cost_provisional", table.historical_cost_provisional),
            SQL(
                "(%s IN %s AND %s IS NOT NULL) AS historical_cost_frozen",
                table.move_type,
                SALE_MOVE_TYPES,
                table.historical_cost,
            ),
            SQL("-%s / NULLIF(%s, 0) AS historical_unit_cost", inventory_value, quantity),
        ]

    def _get_select_expr(self, select_list, alias):
        """Expression of the column `alias` of a _select_list(), without its alias."""
        index = self._get_select_index(select_list, alias)
        code, params, to_flush = select_list[index]._sql_tuple
        code = code.rstrip()
        return SQL(code[: -len(f" AS {alias}")], *params, to_flush=to_flush)  # pylint: disable=sql-injection

    def _replace_select_expr(self, select_list, alias, expr):
        select_list[self._get_select_index(select_list, alias)] = SQL(f"%s AS {alias}", expr)  # pylint: disable=sql-injection

    def _get_select_index(self, select_list, alias):
        suffix = f" AS {alias}"
        for index, item in enumerate(select_list):
            if item._sql_tuple[0].rstrip().endswith(suffix):
                return index
        raise ValueError(f"Column {alias!r} not found in account.invoice.report select list")

    def _read_group_select(self, table: TableSQL, aggregate_spec: str) -> SQL:
        """Quantity-weighted unit cost in company currency, like the core's price_average."""
        if aggregate_spec != "historical_unit_cost:avg_currency":
            return super()._read_group_select(table, aggregate_spec)
        return SQL(
            "COALESCE(-%s / NULLIF(SUM(%s), 0.0), 0)",
            super()._read_group_select(table, "inventory_value:sum_currency"),
            table.quantity,
        )
