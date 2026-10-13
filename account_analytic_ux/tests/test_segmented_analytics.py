# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSegmentedAnalytics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Project = cls.env["project.project"]
        cls.project = Project.create({"name": "Segmented", "use_segmented_analytics": True})
        cls.plain_project = Project.create({"name": "Plain"})
        cls.hours_fname, cls.materials_fname = Project._get_segmented_plan_fnames()
        for project in cls.project | cls.plain_project:
            if not project.account_id:
                project.account_id = cls.env["account.analytic.account"].create(
                    {"name": project.name, "plan_id": cls.env["account.analytic.plan"]._get_all_plans()[0].id}
                )
        cls.employee = cls.env["hr.employee"].create({"name": "Worker", "hourly_cost": 100})

    def _account_count(self, name):
        return self.env["account.analytic.account"].search_count([("name", "=", name)])

    def assert_on_hours_plan(self, line):
        """A segmented timesheet lives on the Hours account and never on Materials."""
        self.assertEqual(line[self.hours_fname], self.project._get_hours_analytic_account())
        self.assertFalse(line[self.materials_fname])

    def test_segmented_project_accounts(self):
        """Given a project with segmentation, when it is created, disabled and enabled again,
        then it gets one Hours and one Materials account, loses them and gets the same ones back."""
        hours = self.project._get_hours_analytic_account()
        materials = self.project._get_materials_analytic_account()
        with self.subTest("creating the project builds both plans and one account per plan"):
            self.assertEqual(hours.name, "Segmented - Horas")
            self.assertEqual(materials.name, "Segmented - Materiales")
            self.assertEqual(hours.plan_id.name, self.project.HOURS_PLAN_NAME)
            self.assertEqual(materials.plan_id.name, self.project.MATERIALS_PLAN_NAME)
            self.assertFalse(self.plain_project[self.hours_fname])
        with self.subTest("disabling the segmentation clears both accounts"):
            self.project.use_segmented_analytics = False
            self.assertFalse(self.project[self.hours_fname])
            self.assertFalse(self.project[self.materials_fname])
        with self.subTest("enabling it again reuses the accounts instead of creating new ones"):
            self.project.use_segmented_analytics = True
            self.assertEqual(self.project[self.hours_fname], hours)
            self.assertEqual(self.project[self.materials_fname], materials)
            self.assertEqual(self._account_count("Segmented - Horas"), 1)
            self.assertEqual(self._account_count("Segmented - Materiales"), 1)

    def test_timesheet_goes_to_hours_plan(self):
        """Given a segmented project, when a timesheet is created and edited, then it is pinned to the
        Hours account with the employee cost, while a plain project timesheet is left untouched."""
        Line = self.env["account.analytic.line"]
        timesheet = Line.create(
            {"name": "work", "project_id": self.project.id, "employee_id": self.employee.id, "unit_amount": 2}
        )
        with self.subTest("the timesheet lands on the Hours account with the employee cost"):
            self.assert_on_hours_plan(timesheet)
            self.assertEqual(timesheet.account_id, self.project.account_id)
            self.assertEqual(timesheet.amount, -200)
        with self.subTest("editing it keeps the Hours account and recomputes the cost"):
            timesheet.write({"unit_amount": 3, self.materials_fname: self.project._get_materials_analytic_account().id})
            self.assert_on_hours_plan(timesheet)
            self.assertEqual(timesheet.amount, -300)
        with self.subTest("a timesheet on a plain project gets no segmented account"):
            plain = Line.create(
                {"name": "work", "project_id": self.plain_project.id, "employee_id": self.employee.id, "unit_amount": 1}
            )
            self.assertFalse(plain[self.hours_fname])
            self.assertEqual(plain.account_id, self.plain_project.account_id)

    def test_picking_cost_goes_to_materials_plan(self):
        """Given a segmented project, when a delivery linked to it is validated, then its analytic line
        is pinned to the Materials account and the project account, without project nor hours account."""
        if "so_line" not in self.env["account.analytic.line"]._fields:
            self.skipTest("the picking line create writes so_line, which needs sale_timesheet installed")
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        warehouse.out_type_id.analytic_costs = True
        product = self.env["product.product"].create({"name": "Brick", "is_storable": True, "standard_price": 50})
        self.env["stock.quant"]._update_available_quantity(product, warehouse.lot_stock_id, 10)
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": customers.id,
                "project_id": self.project.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 2,
                            "location_id": warehouse.lot_stock_id.id,
                            "location_dest_id": customers.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 2
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        line = picking.move_ids.analytic_account_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.category, "picking_entry")
        self.assertEqual(line[self.materials_fname], self.project._get_materials_analytic_account())
        self.assertFalse(line[self.hours_fname])
        self.assertEqual(line.account_id, self.project.account_id)
        self.assertFalse(line.project_id)
        self.assertEqual(line.amount, -100)
