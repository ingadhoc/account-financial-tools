import odoo.tests.common as common
from odoo import Command, fields


class TestAccountUXChangeCurrency(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        self.company_usd = self.env.ref("base.main_company")
        self.partner = self.env.ref("base.res_partner_12")

        self.currency_usd = self.env.ref("base.USD")
        self.currency_ars = self.env.ref("base.ARS")
        self.currency_ars.write({"active": True})

        self.journal_usd = self.env.ref("account.1_sale")

        self.journal_ars = self.journal_usd.copy()

        self.journal_ars.write({"currency_id": self.currency_ars})

    def test_account_ux_change_currency(self):
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                "date": self.today,
                "move_type": "out_invoice",
                "journal_id": self.journal_usd.id,
                "company_id": self.company_usd.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.env.ref("product.product_product_16").id,
                            "quantity": 1,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )

        invoice.write({"journal_id": self.journal_ars.id})

        invoice.action_post()

        self.assertEqual(
            invoice.currency_id,
            self.journal_ars.currency_id,
            "La moneda de la factura no está siendo modificada al cambiar el diario.",
        )

    def test_currency_rate_refresh_on_post_without_invoice_date(self):
        """Test que valida el refresh de currency rate en _post cuando no hay invoice_date.

        Este test valida el cambio implementado en _post() que refresca la tasa de cambio
        cuando no hay invoice_date y la moneda es diferente a la de la compañía.

        Flujo del test:
        1. Crear una factura SIN invoice_date con moneda diferente a la de la compañía
        2. Modificar el rate de la currency para que sea distinto al que tiene la factura
        3. Verificar que al postear, la tasa de cambio se actualiza correctamente
        """
        # Asegurar que la moneda ARS está activa
        self.currency_ars.write({"active": True})

        # Crear tasa de cambio inicial para ARS (por ejemplo, 1000 ARS = 1 USD)
        CurrencyRate = self.env["res.currency.rate"]
        rate_initial = CurrencyRate.create(
            {
                "currency_id": self.currency_ars.id,
                "company_id": self.company_usd.id,
                "name": self.today,
                "rate": 1000.0,  # 1000 ARS por 1 USD
            }
        )

        # Crear factura SIN invoice_date con moneda diferente a la de la compañía
        invoice = self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
                "journal_id": self.journal_ars.id,
                "company_id": self.company_usd.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.env.ref("product.product_product_16").id,
                            "quantity": 1,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )

        # Verificar precondiciones
        self.assertFalse(invoice.invoice_date, "La factura no debe tener invoice_date")
        self.assertNotEqual(
            invoice.currency_id,
            invoice.company_id.currency_id,
            "La moneda de la factura debe ser diferente a la de la compañía",
        )

        # Guardar la tasa inicial de la factura
        initial_rate = invoice.invoice_currency_rate
        self.assertEqual(
            initial_rate,
            1000.0,
            "La tasa inicial debe ser 1000.0",
        )

        # Modificar la tasa de cambio de la moneda (nueva tasa: 1200 ARS = 1 USD)
        rate_initial.write({"rate": 1200.0})

        # Postear la factura
        invoice.action_post()

        # Verificar que la factura está posteada
        self.assertEqual(invoice.state, "posted", "La factura debe estar posteada")

        # Verificar que la tasa de cambio se actualizó al valor actual
        self.assertEqual(
            invoice.invoice_currency_rate,
            1200.0,
            "La tasa de cambio debe actualizarse a 1200.0 después del post",
        )
        self.assertNotEqual(
            invoice.invoice_currency_rate,
            initial_rate,
            "La tasa de cambio debe ser diferente a la inicial",
        )
