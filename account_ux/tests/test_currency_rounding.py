# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account_ux.models.res_currency import ALLOW_ROUNDING_EDIT_PARAM
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import config


@tagged("post_install", "-at_install")
class TestCurrencyRounding(TransactionCase):
    """Tarea 71732: el factor de redondeo de una moneda no se edita a mano.

    El bloqueo aplica solo en bases productivas de cliente, así que los tests
    simulan ese entorno: parámetro ``saas_client.database_uuid`` presente (base
    aprovisionada) y ``server_mode`` vacío (base de tipo Production).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.currency = cls.env["res.currency"].create({"name": "TST", "symbol": "T", "rounding": 0.01})

    def _simulate_client_production(self):
        """Deja el entorno como una base productiva de cliente."""
        self.params.set_param("saas_client.database_uuid", "uuid-de-prueba")
        previous_mode = config.get("server_mode")
        config["server_mode"] = None
        self.addCleanup(config.__setitem__, "server_mode", previous_mode)

    def test_block_and_escape_hatch(self):
        """Bloquea en una base de cliente, y el parámetro lo destraba."""
        self._simulate_client_production()
        self.assertFalse(self.currency.rounding_edit_allowed)
        with self.assertRaisesRegex(UserError, "rounding factor"):
            self.currency.rounding = 0.0001

        self.params.set_param(ALLOW_ROUNDING_EDIT_PARAM, "True")
        self.currency.invalidate_recordset(["rounding_edit_allowed"])
        self.assertTrue(self.currency.rounding_edit_allowed)
        self.currency.rounding = 0.0001
        self.assertEqual(self.currency.decimal_places, 4)

    def test_inert_outside_client_production(self):
        """Sin uuid de base de cliente, o en bases Test / Train / Demo, no molesta."""
        self.params.set_param("saas_client.database_uuid", False)
        self.currency.rounding = 0.001
        self.assertEqual(self.currency.decimal_places, 3)

        self.params.set_param("saas_client.database_uuid", "uuid-de-prueba")
        previous_mode = config.get("server_mode")
        config["server_mode"] = "Test"
        self.addCleanup(config.__setitem__, "server_mode", previous_mode)
        self.currency.rounding = 0.0001
        self.assertEqual(self.currency.decimal_places, 4)

    def test_only_a_real_manual_edit_is_blocked(self):
        """No bloquea reescribir el mismo valor, ni crear, ni la data de los módulos."""
        self._simulate_client_production()

        self.currency.write({"rounding": self.currency.rounding, "position": "before"})
        self.assertEqual(self.currency.position, "before")

        other = self.env["res.currency"].create({"name": "TS1", "symbol": "T", "rounding": 0.05})
        self.assertEqual(other.rounding, 0.05)

        self.currency.with_context(install_mode=True).rounding = 0.001
        self.assertEqual(self.currency.decimal_places, 3)

    def test_parameter_seed(self):
        """La data del módulo lo deja a la vista apagado, sin pisar una habilitación."""
        self.params.search([("key", "=", ALLOW_ROUNDING_EDIT_PARAM)]).unlink()
        self.env["res.currency"]._seed_rounding_edit_param()
        self.assertEqual(self.params.get_param(ALLOW_ROUNDING_EDIT_PARAM), "False")

        self.params.set_param(ALLOW_ROUNDING_EDIT_PARAM, "True")
        self.env["res.currency"]._seed_rounding_edit_param()
        self.assertEqual(self.params.get_param(ALLOW_ROUNDING_EDIT_PARAM), "True")
