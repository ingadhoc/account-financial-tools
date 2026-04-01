from odoo.tests.common import TransactionCase


class TestAccountDebtReport(TransactionCase):
    def setUp(self):
        super(TestAccountDebtReport, self).setUp()
        # Set up test data, e.g., a partner and invoices
        self.partner = self.env["res.partner"].create({"name": "Test Partner", "email": "test@example.com"})

    def test_format_debt_report_amount(self):
        amount = self.partner._format_debt_report_amount(-278300, self.env.company.currency_id)
        self.assertTrue(amount.startswith("- "))
        self.assertIn(self.env.company.currency_id.symbol, amount)

    def test_format_debt_report_line_keeps_raw_values(self):
        formatted_line = self.partner._format_debt_report_line(
            {
                "amount": 1500.0,
                "amount_residual": 500.0,
                "balance": 2000.0,
                "amount_currency": 100.0,
                "amount_residual_currency": 50.0,
                "balance_currency": 150.0,
                "currency_name": "USD",
            },
            company_currency=self.env.company.currency_id,
            secondary_currency=self.env.ref("base.USD"),
        )
        self.assertEqual(formatted_line["amount_raw"], 1500.0)
        self.assertEqual(formatted_line["amount_currency_raw"], 100.0)
        self.assertIn(self.env.company.currency_id.symbol, formatted_line["amount"])
        self.assertTrue(formatted_line["amount_currency"].startswith("USD "))

    def test_debt_report_lines(self):
        # Execute the method and validate output
        report_lines = self.partner._get_debt_report_lines()
        # Perform assertions to verify the behavior
        self.assertIsInstance(report_lines, list, "Expected a list of report lines")
        if report_lines:
            first_line = report_lines[0]
            self.assertIn("date", first_line, "Report line should contain 'date'")
            self.assertIn("name", first_line, "Report line should contain 'name'")
            self.assertIn("balance", first_line, "Report line should contain 'balance'")


class TestAccountDebtReportWizard(TransactionCase):
    def setUp(self):
        super(TestAccountDebtReportWizard, self).setUp()
        # Crear un partner de prueba
        self.partner = self.env["res.partner"].create({"name": "Test Partner", "email": "test@example.com"})
        # Crear el wizard para el reporte de deuda
        self.wizard = self.env["account.debt.report.wizard"].create(
            {
                "company_id": self.env.company.id,
                "result_selection": "all",
                "historical_full": True,
            }
        )

    def test_confirm_method(self):
        # Verificar que el método confirm se ejecuta correctamente
        action = self.wizard.with_context(active_ids=[self.partner.id]).confirm()
        self.assertTrue(action, "El método confirm debería retornar una acción de reporte")

    def test_send_by_email_method(self):
        # Verificar que el método send_by_email se ejecuta correctamente
        action = self.wizard.with_context(active_id=self.partner.id).send_by_email()
        self.assertTrue(action, "El método send_by_email debería retornar una acción de ventana")
        self.assertEqual(action["res_model"], "mail.compose.message", "El modelo debería ser 'mail.compose.message'")
