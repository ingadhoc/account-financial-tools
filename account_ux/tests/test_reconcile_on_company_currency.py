# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestReconcileOnCompanyCurrency(AccountTestInvoicingCommon):
    """Regresión del bug del residual en moneda secundaria al conciliar con
    ``reconcile_on_company_currency`` activo.

    Escenario: una compañía con ``reconcile_on_company_currency`` concilia un
    apunte en moneda de compañía contra uno en moneda secundaria, dejando una
    diferencia de redondeo. El override de ``_prepare_reconciliation_single_partial``
    concilia en moneda de compañía (shadow), y debe reexpresar el residual
    sobrante en la moneda secundaria real a la cotización del comprobante.

    Antes del fix el residual quedaba con el valor en moneda de compañía pero
    asociado a un apunte cuya ``currency_id`` es la secundaria, lo que hacía que
    el wizard de ajuste lo multiplicara por la cotización y propusiera un importe
    inflado (ver caso real ND-A vs RE-X: 624,79 ARS -> 900.010 ARS).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        # reconcile_on_company_currency sólo se permite con país Argentina.
        # Las compañías argentinas exigen redondeo global (constraint de
        # saas_client_l10n_ar); lo seteamos junto con el país para no pegar
        # contra un estado intermedio inválido.
        cls.company.write(
            {
                "country_id": cls.env.ref("base.ar").id,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        cls.company.reconcile_on_company_currency = True
        cls.company_currency = cls.company_data["currency"]
        # 1 unidad de moneda de compañía = 1000 unidades de la moneda secundaria
        cls.foreign_currency = cls.setup_other_currency("EUR", rates=[("2016-01-01", 1000.0)])
        cls.receivable = cls.company_data["default_account_receivable"]
        # El override exige que la cuenta no fuerce una moneda propia.
        cls.receivable.currency_id = False
        cls.date = fields.Date.from_string("2016-01-01")

    def _receivable_line(self, balance, currency, amount_currency):
        """Crea un asiento posteado con una línea sobre la cuenta a cobrar y la
        contrapartida en una cuenta de ingresos, y devuelve la línea a cobrar."""
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.date,
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.receivable.id,
                            "balance": balance,
                            "currency_id": currency.id,
                            "amount_currency": amount_currency,
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data["default_account_revenue"].id,
                            "balance": -balance,
                            "currency_id": currency.id,
                            "amount_currency": -amount_currency,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(lambda line: line.account_id == self.receivable)

    def test_residual_currency_expressed_in_secondary_currency(self):
        # Débito en moneda de compañía (como la ND en ARS): 99,50.
        debit_line = self._receivable_line(99.50, self.company_currency, 99.50)
        # Crédito en moneda secundaria (como el recibo en USD): -100.000 EUR @ 1000 = -100 de compañía.
        credit_line = self._receivable_line(-100.0, self.foreign_currency, -100000.0)

        debit_values = {
            "aml": debit_line,
            "amount_residual": debit_line.amount_residual,
            "amount_residual_currency": debit_line.amount_residual_currency,
        }
        credit_values = {
            "aml": credit_line,
            "amount_residual": credit_line.amount_residual,
            "amount_residual_currency": credit_line.amount_residual_currency,
        }

        res = self.env["account.move.line"]._prepare_reconciliation_single_partial(debit_values, credit_values)

        # El débito (99,50) se cancela por completo.
        self.assertIsNone(res["debit_values"])
        # Sobra residual en el crédito: 0,50 de moneda de compañía.
        self.assertAlmostEqual(res["credit_values"]["amount_residual"], -0.50)
        # El residual en moneda secundaria debe ser su equivalente a la cotización
        # del comprobante (0,50 * 1000 = 500 EUR), NO el valor en moneda de compañía (0,50).
        self.assertAlmostEqual(res["credit_values"]["amount_residual_currency"], -500.0)
        # El partial cancela 99,50 de compañía = 99.500 EUR a la cotización del recibo.
        self.assertAlmostEqual(res["partial_values"]["amount"], 99.50)
        self.assertAlmostEqual(res["partial_values"]["credit_amount_currency"], 99500.0)

    def test_rounding_residual_does_not_create_exchange_move(self):
        """Con ``reconcile_on_company_currency`` activo, conciliar dos apuntes en la misma moneda
        secundaria que cierran exacto en secundaria pero difieren por redondeo en moneda de compañía
        NO debe generar un asiento de diferencia de cambio (la promesa del setting)."""
        exchange_journal = self.company.currency_exchange_journal_id
        domain = [("journal_id", "=", exchange_journal.id)]
        moves_before = self.env["account.move"].search_count(domain)
        # Cierran exacto en moneda secundaria (100.000 EUR) pero difieren 0,01 en moneda de compañía.
        debit_line = self._receivable_line(100.01, self.foreign_currency, 100000.0)
        credit_line = self._receivable_line(-100.00, self.foreign_currency, -100000.0)

        (debit_line + credit_line).reconcile()

        self.assertEqual(
            self.env["account.move"].search_count(domain),
            moves_before,
            "No debe crearse un asiento de diferencia de cambio por el residuo de redondeo.",
        )
