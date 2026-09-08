# © 2026 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.addons.stock_account.tests.common import TestStockValuationCommon
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestHistoricalCostPost(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Service Product",
                "type": "service",
                "standard_price": 30.0,
                "list_price": 100.0,
            }
        )

    def _create_customer_invoice(self, product, quantity=1.0, price_unit=None, move_type="out_invoice", post=True):
        move_form = Form(self.env["account.move"].with_context(default_move_type=move_type))
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = quantity
            if price_unit is not None:
                line_form.price_unit = price_unit
            line_form.tax_ids.clear()
        invoice = move_form.save()
        if post:
            invoice.action_post()
        return invoice

    def _product_line(self, invoice):
        return invoice.line_ids.filtered(lambda l: l.display_type == "product")

    def test_ac1_price_unaffected_by_cost_change(self):
        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6, price_unit=1000)
        line = self._product_line(invoice)
        historical_cost_before = line.historical_cost

        report_before = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        margin_before = report_before.price_margin
        inventory_value_before = report_before.inventory_value

        product.standard_price = 150.0

        report_after = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        self.assertEqual(line.historical_cost, historical_cost_before)
        self.assertAlmostEqual(report_after.price_margin, margin_before)
        self.assertAlmostEqual(report_after.inventory_value, inventory_value_before)

    def test_ac5_service_product_provisional(self):
        self.service_product.standard_price = 30.0
        invoice = self._create_customer_invoice(self.service_product, quantity=2)
        line = self._product_line(invoice)
        self.assertTrue(line.historical_cost_provisional)
        self.assertEqual(line.historical_cost, 60.0)

        self.service_product.standard_price = 999.0
        self.assertEqual(line.historical_cost, 60.0)

    def test_ac5_storable_no_delivery_provisional(self):
        product = self.product_fifo
        invoice = self._create_customer_invoice(product, quantity=3, price_unit=1000)
        line = self._product_line(invoice)
        self.assertTrue(line.historical_cost_provisional)
        self.assertEqual(line.historical_cost, 3 * product.standard_price)

    def test_ac7_null_historical_cost_no_regression(self):
        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6, price_unit=1000)
        line = self._product_line(invoice)
        # Simulates an invoice posted before this module was installed:
        # historical_cost is SQL NULL, not 0.0 (writing False through the ORM
        # on a Monetary field stores 0.0, so this uses the same raw-SQL path
        # as _clear_historical_cost).
        line._clear_historical_cost()

        report = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        expected_inventory_value = -6 * product.standard_price
        self.assertAlmostEqual(report.inventory_value, expected_inventory_value)

    def test_ac10_draft_clears_and_repost(self):
        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6, price_unit=1000)
        line = self._product_line(invoice)
        self.assertTrue(line.historical_cost)

        invoice.button_draft()
        self.assertFalse(line.historical_cost)
        self.assertFalse(line.historical_cost_provisional)

        line.quantity = 10
        invoice.action_post()
        self.assertEqual(line.historical_cost, 10 * product.standard_price)

    def test_ac15_purchase_untouched(self):
        product = self.product_standard
        move_form = Form(self.env["account.move"].with_context(default_move_type="in_invoice"))
        move_form.partner_id = self.vendor
        move_form.invoice_date = fields.Date.today()
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = 4
            line_form.price_unit = 100
            line_form.tax_ids.clear()
        bill = move_form.save()
        bill.action_post()
        line = self._product_line(bill)
        self.assertFalse(line.historical_cost)

        report = self.env["account.invoice.report"].search([("move_id", "=", bill.id)])
        self.assertAlmostEqual(report.inventory_value, 4 * product.standard_price)

    def test_ac17_negative_quantity_line_sign(self):
        product = self.product_standard
        move_form = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = 5
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = -2
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
        invoice = move_form.save()
        invoice.action_post()

        negative_line = invoice.line_ids.filtered(lambda l: l.display_type == "product" and l.quantity == -2)
        # historical_cost follows line.quantity's own sign (§1 of the spec),
        # so a negative-quantity line inside an out_invoice comes out negative.
        self.assertEqual(negative_line.historical_cost, -2 * product.standard_price)

    def test_ac6_multi_company_with_company(self):
        product = self.product_standard
        product.with_company(self.company).standard_price = 100.0
        product.with_company(self.other_company).standard_price = 500.0

        invoice = (
            self.env["account.move"]
            .with_company(self.other_company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "company_id": self.other_company.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "quantity": 3,
                                "price_unit": 1000,
                                "tax_ids": [],
                            },
                        )
                    ],
                }
            )
        )
        # Active company stays self.company (the env we're running under);
        # _post() must still resolve each move's OWN company, not the active
        # one, when posting a batch that mixes companies.
        invoice.action_post()

        line = self._product_line(invoice)
        self.assertAlmostEqual(line.historical_cost, 3 * 500.0)

    def test_ac8_uom_conversion(self):
        product = self.product_standard
        product.standard_price = 100.0
        move_form = Form(self.env["account.move"].with_context(default_move_type="out_invoice"))
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.product_uom_id = self.uom_pack_of_6
            line_form.quantity = 2
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
        invoice = move_form.save()
        invoice.action_post()

        line = self._product_line(invoice)
        # 2 packs of 6 = 12 units, at 100/unit.
        self.assertAlmostEqual(line.historical_cost, 12 * 100.0)

    def test_ac9_credit_note_is_opposite_of_invoice(self):
        product = self.product_standard
        invoice = self._create_customer_invoice(product, quantity=6, price_unit=1000)
        line = self._product_line(invoice)

        credit_note = self._refund(invoice)
        credit_line = self._product_line(credit_note)

        # historical_cost is signed as line.quantity (§1), and quantity on a
        # credit note line is the same positive magnitude as on the invoice
        # — the move_type sign flip lives only in the report's _select(), not
        # on the line-level field. So both lines carry the same value here;
        # what has to be opposite is the REPORT's price_margin, checked below.
        self.assertAlmostEqual(credit_line.historical_cost, line.historical_cost)

        report_invoice = self.env["account.invoice.report"].search([("move_id", "=", invoice.id)])
        report_credit_note = self.env["account.invoice.report"].search([("move_id", "=", credit_note.id)])
        self.assertAlmostEqual(report_invoice.price_margin, -report_credit_note.price_margin)

    def test_ac11_query_count_bounded(self):
        # Not a tight equality: assertQueryCount only fails if the actual
        # count goes OVER the ceiling, so this is a regression guard against
        # an N+1 introduced later, not a brittle exact-count pin. Baseline
        # measured on this suite; bump it (with a comment why) if a
        # legitimate change moves it.
        product = self.product_standard_auto  # real_time: no extra query vs core
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 3,
                            "price_unit": 1000,
                            "tax_ids": [(5, 0, 0)],
                        },
                    )
                ],
            }
        )
        with self.assertQueryCount(default=140):  # baseline measured: 115
            invoice.action_post()

    def test_move_reverse_cancel_not_excluded(self):
        # Unlike stock_account._post, our override does NOT early-return under
        # move_reverse_cancel (§2 of the spec) — a cancellation credit note
        # still needs its cost frozen, otherwise invoice + reversal wouldn't
        # net to zero margin.
        product = self.product_standard
        move_form = Form(self.env["account.move"].with_context(default_move_type="out_refund"))
        move_form.partner_id = self.partner
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = product
            line_form.quantity = 6
            line_form.price_unit = 1000
            line_form.tax_ids.clear()
        credit_note = move_form.save()
        credit_note.with_context(move_reverse_cancel=True)._post(soft=False)

        line = self._product_line(credit_note)
        self.assertTrue(line.historical_cost)
        self.assertEqual(line.historical_cost, line.quantity * product.standard_price)
