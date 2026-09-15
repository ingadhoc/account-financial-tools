# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account_ux.models.res_currency import ALLOW_ROUNDING_EDIT_PARAM
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCurrencyRounding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.currency = cls.env["res.currency"].create({"name": "TST", "symbol": "T", "rounding": 0.01})

    def _enable_guard(self):
        # the guard is skipped while tests run, so simulate a regular server
        self.patch(self.registry["res.currency"], "_skip_rounding_guard", lambda self: False)

    def test_block_and_escape_hatch(self):
        """Blocked by default, and the system parameter lifts it."""
        self._enable_guard()
        self.assertFalse(self.currency.rounding_edit_allowed)
        with self.assertRaisesRegex(UserError, "rounding factor"):
            self.currency.rounding = 0.0001

        self.params.set_param(ALLOW_ROUNDING_EDIT_PARAM, "True")
        self.currency.invalidate_recordset(["rounding_edit_allowed"])
        self.assertTrue(self.currency.rounding_edit_allowed)
        self.currency.rounding = 0.0001
        self.assertEqual(self.currency.decimal_places, 4)

    def test_inert_while_running_tests(self):
        """Other modules tests can still change the rounding, but the form keeps it read-only."""
        self.assertFalse(self.currency.rounding_edit_allowed)
        self.currency.rounding = 0.001
        self.assertEqual(self.currency.decimal_places, 3)

    def test_only_a_real_manual_edit_is_blocked(self):
        """Rewriting the same value, creating and the modules data are not blocked, but a faked install_mode is."""
        self._enable_guard()

        self.currency.write({"rounding": self.currency.rounding, "position": "before"})
        self.assertEqual(self.currency.position, "before")

        other = self.env["res.currency"].create({"name": "TS1", "symbol": "T", "rounding": 0.05})
        self.assertEqual(other.rounding, 0.05)

        with self.assertRaisesRegex(UserError, "rounding factor"):
            self.currency.with_context(install_mode=True).rounding = 0.001

        self.patch(self.registry, "ready", False)
        self.currency.rounding = 0.001
        self.assertEqual(self.currency.decimal_places, 3)

    def test_parameter_seed(self):
        """The module data creates it disabled, without overriding an enabled one."""
        self.params.search([("key", "=", ALLOW_ROUNDING_EDIT_PARAM)]).unlink()
        self.env["res.currency"]._seed_rounding_edit_param()
        self.assertEqual(self.params.get_param(ALLOW_ROUNDING_EDIT_PARAM), "False")

        self.params.set_param(ALLOW_ROUNDING_EDIT_PARAM, "True")
        self.env["res.currency"]._seed_rounding_edit_param()
        self.assertEqual(self.params.get_param(ALLOW_ROUNDING_EDIT_PARAM), "True")
