# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.models import TableSQL
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    # referencia a company currency en string y help
    price_subtotal = fields.Monetary(
        string="Untaxed Total (CC)",
        help="Untaxed Total in the company's currency where it is set",
    )
    price_average = fields.Monetary(
        string="Average Price (CC)",
        help="Average Price in the company's currency where it is set",
    )
    price_margin = fields.Monetary(string="Margin (CC)", help="Margin in the company's currency where it is set")
    # creamos nuevos campos para tener descuentos, vinculos e importes en moneda de compañía
    total_cc = fields.Monetary(
        string="Total (CC)",
        readonly=True,
        help="Taxed Total in the company's currency where it is set",
        currency_field="company_currency_id",
        aggregator="sum_currency",
    )
    line_id = fields.Many2one("account.move.line", string="Journal Item", readonly=True)
    price_unit = fields.Monetary(
        "Unit Price",
        readonly=True,
        currency_field="currency_id",
    )
    discount = fields.Float("Discount (%)", readonly=True)
    discount_amount = fields.Monetary(
        readonly=True,
        aggregator="sum",
        currency_field="currency_id",
    )

    def _select_list(self, table: TableSQL):
        refund_sign = SQL(
            "CASE WHEN %s IN ('in_refund', 'out_refund', 'in_receipt') THEN -1 ELSE 1 END", table.move_id.move_type
        )
        return super()._select_list(table) + [
            SQL("%s AS line_id", table.id),
            table.price_unit,
            table.discount,
            SQL(
                "%s * %s * %s / 100 * %s AS discount_amount",
                table.price_unit,
                table.quantity,
                table.discount,
                refund_sign,
            ),
            SQL(
                "-%s * (%s / NULLIF(%s, 0.0)) AS total_cc",
                table.balance,
                table.price_total,
                table.price_subtotal,
            ),
        ]
