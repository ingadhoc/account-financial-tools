import odoo.tests.common as common
from odoo import Command, fields


class TestStockAccountUx(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.partner_ri = self.env["res.partner"].search([("name", "=", "ADHOC SA")], limit=1)

        self.product_category = self.env.ref("product.product_category_5")
        self.product_category.property_cost_method = "fifo"
        self.product = self.env["product.product"].search(
            [("active", "=", True), ("categ_id", "=", self.product_category.id)], limit=1
        )

    def test_stock_account_ux(self):
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_ri.id,
                "date_order": self.today,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_qty": 1, "price_unit": 100}),
                ],
            }
        )
        purchase_order.button_confirm()
        # Validate picking
        action = purchase_order.action_view_picking()
        in_picking = self.env[action["res_model"]].browse(action["res_id"])
        in_picking.move_ids.quantity = 1
        in_picking.move_ids.picked = True
        in_picking.button_validate()

        # Create bill invoice
        bill = self.env["account.move"].browse(purchase_order.action_create_invoice()["res_id"])
        bill.invoice_date = self.today
        bill.purchase_id = purchase_order
        bill.action_post()

        bill.button_draft()
        # Create stock_valuation_layer_ids by modifying the price_unit
        bill.invoice_line_ids.price_unit = 120
        bill.action_post()

        self.assertTrue(bill.allow_move_with_valuation_cancelation)
