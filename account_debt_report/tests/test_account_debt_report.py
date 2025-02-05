from odoo.tests.common import TransactionCase


class TestAccountDebtReport(TransactionCase):
    def setUp(self):
        super(TestAccountDebtReport, self).setUp()
        # Set up test data, e.g., a partner and invoices
        self.partner = self.env["res.partner"].create({"name": "Test Partner", "email": "test@example.com"})

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
