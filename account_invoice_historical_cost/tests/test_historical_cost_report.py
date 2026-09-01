# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestHistoricalCostReport(TestStockValuationCommon):
    def _create_customer_invoice(self, product, quantity, price_unit=1000):
        move_form = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = quantity
            line_form.price_unit = price_unit
            line_form.tax_ids.clear()
        invoice = move_form.save()
        invoice.action_post()
        return invoice

    def test_ac12b_read_and_search(self):
        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6)

        report = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        self.assertTrue(report.read(["historical_cost", "inventory_value", "price_margin"]))

        found_provisional = self.env["account.invoice.report"].search(
            [
                ("move_id", "=", invoice.id),
                ("historical_cost_provisional", "=", True),
            ]
        )
        self.assertEqual(found_provisional, report)

        ordered = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)], order="price_margin desc")
        self.assertEqual(ordered, report)

    def test_ac12b_order_by_price_margin(self):
        product = self.product_standard
        product.standard_price = 100.0
        low_margin_invoice = self._create_customer_invoice(product, quantity=1, price_unit=150)
        product.standard_price = 10.0
        high_margin_invoice = self._create_customer_invoice(product, quantity=1, price_unit=150)

        ordered = self.env["account.invoice.report"].search(
            [("move_id", "in", (low_margin_invoice | high_margin_invoice).ids)],
            order="price_margin desc",
        )
        self.assertEqual(ordered.mapped("move_id"), (high_margin_invoice | low_margin_invoice))

    def test_ac13_chained_overrides_with_account_ux_and_personalizations(self):
        # Requires account_ux and personalizations_adhoc installed: if either
        # of their _select() append columns disappeared, this would error out
        # reading them, or our own append would have broken the SELECT.
        installed = self.env["ir.module.module"].search(
            [
                ("name", "in", ["account_ux", "personalizations_adhoc"]),
                ("state", "=", "installed"),
            ]
        )
        if len(installed) < 2:
            self.skipTest("account_ux and personalizations_adhoc must both be installed")

        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6)
        report = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        values = report.read(["total_cc", "discount", "historical_cost", "price_margin", "inventory_value"])[0]
        self.assertTrue(values)

    def test_ac14_weighted_unit_cost(self):
        product = self.product_standard
        product.standard_price = 100.0
        invoice_1 = self._create_customer_invoice(product, quantity=2)
        product.standard_price = 50.0
        invoice_2 = self._create_customer_invoice(product, quantity=8)

        groups = self.env["account.invoice.report"]._read_group(
            [("move_id", "in", (invoice_1 | invoice_2).ids)],
            groupby=["product_id"],
            aggregates=["historical_unit_cost:avg"],
        )
        self.assertEqual(len(groups), 1)
        _, weighted_unit_cost = groups[0]
        # (2*100 + 8*50) / 10 = 60, not the simple average of 100 and 50 (75).
        self.assertAlmostEqual(weighted_unit_cost, 60.0)
