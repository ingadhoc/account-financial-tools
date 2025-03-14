# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    current_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Current Company Currency",
        compute="_compute_current_currency_id",
        store=False,
    )
    # agregamos widgets monetary, referencia a company currency en string y help
    price_subtotal = fields.Monetary(
        currency_field="current_currency_id",
        string="Untaxed Total (CC)",
        help="Untaxed Total in the company's currency where it is set",
    )
    price_total = fields.Monetary(string="Total", currency_field="currency_id")
    price_average = fields.Monetary(
        currency_field="current_currency_id",
        string="Average Price (CC)",
        help="Average Price in the company's currency where it is set",
    )
    price_margin = fields.Float(string="Margin (CC)", help="Margin in the company's currency where it is set")
    # creamos nuevos campos para tener descuentos, vinculos e importes en moneda de compañía
    total_cc = fields.Monetary(
        string="Total (CC)",
        readonly=True,
        help="Untaxed Total in the company's currency where it is set",
        currency_field="current_currency_id",
    )
    line_id = fields.Many2one("account.move.line", string="Journal Item", readonly=True)
    price_subtotal_currency = fields.Monetary(string="Untaxed Amount in Currency", currency_field="currency_id")
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

    _depends = {"account.move.line": ["price_unit", "discount"]}

    def _select(self):
        query = SQL("""
                , line.price_unit
                , line.id as line_id
                , line.discount
                , line.price_unit * line.quantity * line.discount / 100 *
                    (CASE WHEN move.move_type IN ('in_refund', 'out_refund', 'in_receipt') THEN -1 ELSE 1 END) as discount_amount
                , -line.balance * (line.price_total / NULLIF(line.price_subtotal, 0.0)) * account_currency_table.rate AS total_cc
            """)
        return SQL("%s %s", super()._select(), query)

    @api.depends("company_id")
    def _compute_current_currency_id(self):
        for record in self:
            record.current_currency_id = self.env.company.currency_id
