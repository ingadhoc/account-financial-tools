from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestExchangeDifferenceInvoice(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template("ar_ri")
    def setUpClass(cls):
        super().setUpClass()

        # Crear data mínima necesaria antes de cargar demo data
        cls._ensure_demo_dependencies()

        # Cargar demo data del módulo (esto crea las facturas, pagos y diferencias de cambio)
        chart = cls.env["account.chart.template"]
        chart._install_exchange_diff_demo(cls.company)

        # Referenciar la data de demo cargada
        cls._setup_demo_references(chart)

        # Configurar journals necesarios para tests
        cls._setup_journals()

    @classmethod
    def _ensure_demo_dependencies(cls):
        """Crear dependencies mínimas para que funcione la demo data."""
        # Crear partners de demo si no existen
        if not cls.env.ref("l10n_ar_tax.res_partner_adhoc_caba", raise_if_not_found=False):
            cls.env["res.partner"]._load_records(
                [
                    {
                        "xml_id": "l10n_ar_tax.res_partner_adhoc_caba",
                        "noupdate": True,
                        "values": {
                            "name": "AdHoc CABA",
                            "vat": "30714282611",
                            "country_id": cls.env.ref("base.ar").id,
                            "company_type": "company",
                        },
                    }
                ]
            )

        if not cls.env.ref("l10n_ar.res_partner_gritti_agrimensura", raise_if_not_found=False):
            cls.env["res.partner"]._load_records(
                [
                    {
                        "xml_id": "l10n_ar.res_partner_gritti_agrimensura",
                        "noupdate": True,
                        "values": {
                            "name": "Gritti Agrimensura",
                            "vat": "30000000009",
                            "country_id": cls.env.ref("base.ar").id,
                            "company_type": "company",
                        },
                    }
                ]
            )

        # Crear producto de demo si no existe
        if not cls.env.ref("product.product_product_2", raise_if_not_found=False):
            cls.env["product.product"]._load_records(
                [
                    {
                        "xml_id": "product.product_product_2",
                        "noupdate": True,
                        "values": {"name": "Service Product", "type": "service", "list_price": 100.0},
                    }
                ]
            )

    @classmethod
    def _setup_demo_references(cls, chart):
        """Configurar referencias a la data de demo."""
        cls.partner_adhoc = cls.env.ref("l10n_ar_tax.res_partner_adhoc_caba")
        cls.partner_gritti = cls.env.ref("l10n_ar.res_partner_gritti_agrimensura")
        cls.product_service = cls.env.ref("product.product_product_2")
        cls.product_exchange_diff = chart.ref("product_exchange_difference")

        # Facturas de demo
        cls.demo_invoices = cls.env["account.move"]
        for xmlid in ["demo_invoice_1", "demo_invoice_2", "demo_invoice_3", "demo_invoice_4"]:
            cls.demo_invoices |= chart.ref(xmlid)

        cls.demo_cash_usd = chart.ref("demo_cash_usd")

    @classmethod
    def _setup_journals(cls):
        """Configurar journals necesarios para tests."""
        cls.exchange_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id), ("code", "=", "EXCH")], limit=1
        )

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )

    def _get_unprocessed_exchange_entries(self, limit=None, partner_ids=None):
        """Helper para obtener entradas de diferencia de cambio no procesadas."""
        domain = [
            ("journal_id", "=", self.exchange_journal.id),
            ("account_type", "=", "asset_receivable"),
            ("move_type", "=", "entry"),
            ("move_id.exchange_reversal_id", "=", False),
            ("move_id.exchange_reversed_move_ids", "=", False),
        ]
        if partner_ids:
            domain.append(("partner_id", "in", partner_ids))

        return self.env["account.move.line"].search(domain, limit=limit)

    # ==================== TESTS DE FUNCIONALIDAD CORE ====================

    def test_01_exchange_info_computed_field(self):
        """Test 01 - Verifies exchange_info computed field shows correct information and updates after processing."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)
        if not exchange_entries:
            self.skipTest("No hay entradas de diferencia de cambio para probar")

        entry = exchange_entries[0]
        self.assertTrue(entry.exchange_info, "exchange_info debe tener contenido")
        self.assertIn("Exchange diff for:", entry.exchange_info)

        # Test que después de procesar cambia el estado
        wizard = self._create_wizard_for_entries(exchange_entries)
        wizard.action_create_debit_credit_notes()

        entry._invalidate_cache(["exchange_info"])
        self.assertIn("Debit Note Issued", entry.exchange_info)

    def test_02_domain_filter_unprocessed_entries(self):
        """Test 02 - Tests domain filter returns only unprocessed exchange entries."""
        aml = self.env["account.move.line"].with_company(self.company)
        domain = aml._get_exchange_difference_domain()

        # Verificar elementos clave del dominio
        expected_clauses = [
            ("journal_id", "=", self.exchange_journal.id),
            ("account_type", "=", "asset_receivable"),
            ("move_type", "=", "entry"),
        ]

        for clause in expected_clauses:
            self.assertIn(clause, domain, f"Dominio debe contener {clause}")

        # Verificar que el dominio funciona
        entries = aml.search(domain)
        for entry in entries:
            self.assertEqual(entry.journal_id, self.exchange_journal)
            self.assertEqual(entry.account_type, "asset_receivable")

    def test_03_exchange_difference_action(self):
        """Test 03 - Verifies exchange difference action opens with correct filters and context."""
        action = self.env["account.move.line"].action_exchange_difference()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move.line")
        self.assertEqual(action["view_mode"], "list")

        # Verificar filtros por defecto
        context = action.get("context", {})
        self.assertIn("search_default_to_process", context)
        self.assertIn("search_default_current_month", context)

    # ==================== TESTS DE WIZARD ====================

    def _create_wizard_for_entries(self, exchange_entries):
        """Helper para crear wizard con entradas específicas."""
        return (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=exchange_entries.ids)
            .create({"journal_id": self.sale_journal.id})
        )

    def test_04_wizard_data_grouping_and_validation(self):
        """Test 04 - Tests wizard opens, groups exchange entries by partner and validates basic requirements."""
        exchange_entries = self._get_unprocessed_exchange_entries()
        if not exchange_entries:
            self.skipTest("No hay entradas de diferencia de cambio para probar")

        wizard = self._create_wizard_for_entries(exchange_entries)

        # Verificar que el wizard tiene líneas agrupadas por partner
        self.assertTrue(wizard.line_ids, "El wizard debe tener líneas")

        # Verificar partners y balances
        wizard_partners = wizard.line_ids.mapped("partner_id")
        self.assertTrue(wizard_partners, "El wizard debe tener partners asignados")

        for line in wizard.line_ids:
            self.assertIsNotNone(line.balance, "El balance debe estar calculado")
            self.assertIsInstance(line.balance, (int, float), "Balance debe ser numérico")

        # Test validación de entradas vacías
        with self.assertRaises(UserError):
            wizard._validate_entries_to_process(self.env["account.move.line"])

    def test_05_wizard_fiscal_position_modes(self):
        """Test 05 - Tests wizard with automatic and manual fiscal position override modes."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)
        if not exchange_entries:
            self.skipTest("No hay entradas para probar")

        # Test modo automático (por defecto)
        wizard_auto = self._create_wizard_for_entries(exchange_entries)
        self.assertEqual(wizard_auto.fiscal_position, "automatic")

        # Test modo manual con posición fiscal
        fiscal_position = self.env["account.fiscal.position"].search([("company_id", "=", self.company.id)], limit=1)

        if fiscal_position:
            wizard_manual = (
                self.env["account.exchange.difference.wizard"]
                .with_context(move_line_ids=exchange_entries.ids)
                .create(
                    {
                        "journal_id": self.sale_journal.id,
                        "fiscal_position": "manual",
                        "fiscal_position_id": fiscal_position.id,
                    }
                )
            )

            self.assertEqual(wizard_manual.fiscal_position, "manual")
            self.assertEqual(wizard_manual.fiscal_position_id, fiscal_position)

    # ==================== TESTS DE PROCESAMIENTO Y CONCILIACIÓN ====================

    def test_06_complete_debit_credit_note_workflow(self):
        """Test 06 - Validates full workflow: wizard creates debit/credit notes, ensures reversal entries are posted and reconciled correctly, verifies messages are posted to related payment records."""
        exchange_entries = self._get_unprocessed_exchange_entries()
        if not exchange_entries:
            self.skipTest("No hay entradas de diferencia de cambio para probar")

        initial_count = len(exchange_entries)
        self.assertGreater(initial_count, 0, "Debe haber entradas para procesar")

        # Obtener pagos relacionados antes del procesamiento para verificar mensajes
        partial_reconciles = self.env["account.partial.reconcile"].search(
            [("exchange_move_id", "in", exchange_entries.mapped("move_id").ids)]
        )
        related_payments = (
            (partial_reconciles.mapped("debit_move_id") + partial_reconciles.mapped("credit_move_id"))
            .filtered(lambda l: l.move_type == "entry")
            .mapped("payment_id")
            .filtered(lambda p: p)
        )
        initial_message_counts = {payment.id: len(payment.message_ids) for payment in related_payments}

        # Crear y ejecutar wizard
        wizard = self._create_wizard_for_entries(exchange_entries)
        action = wizard.action_create_debit_credit_notes()

        # Verificar que se crearon notas de débito/crédito
        if action and isinstance(action, dict) and action.get("domain"):
            created_notes = self.env["account.move"].search(action["domain"])
            non_zero_lines = wizard.line_ids.filtered(lambda l: l.balance != 0)

            self.assertEqual(
                len(created_notes), len(non_zero_lines), "Debe crear una nota por partner con balance != 0"
            )

            # Verificar que las notas están en estado correcto
            for note in created_notes:
                self.assertIn(note.state, ["draft", "posted"], "Las notas deben estar creadas")

                # Verificar que usa el producto de diferencia de cambio
                if self.company.exchange_difference_product:
                    self.assertIn(self.company.exchange_difference_product, note.invoice_line_ids.mapped("product_id"))

        # Verificar que los movimientos de intercambio fueron marcados como procesados
        exchange_moves = exchange_entries.mapped("move_id")
        for move in exchange_moves:
            self.assertTrue(move.exchange_reversal_id, f"Movimiento {move.name} debe tener exchange_reversal_id")

        # Verificar conciliación y reversión
        for move in exchange_moves:
            reversal_move = move.exchange_reversal_id
            if reversal_move:
                self.assertEqual(reversal_move.state, "posted", "Reversión debe estar posteada")

                # Verificar que hay líneas de conciliación
                exchange_line = exchange_entries.filtered(lambda l: l.move_id == move)
                if exchange_line:
                    reversal_line = reversal_move.line_ids.filtered(
                        lambda l: l.account_id == exchange_line.account_id and l.partner_id == exchange_line.partner_id
                    )
                    self.assertTrue(reversal_line, "Debe haber línea de reversión correspondiente")

                    # Verificar conciliación
                    self.assertTrue(
                        exchange_line.matched_debit_ids
                        or exchange_line.matched_credit_ids
                        or exchange_line.full_reconcile_id,
                        "La línea de intercambio debe estar conciliada",
                    )

        # Verificar mensajes en pagos relacionados
        for payment in related_payments:
            current_message_count = len(payment.message_ids)
            self.assertGreater(
                current_message_count,
                initial_message_counts.get(payment.id, 0),
                f"Pago {payment.name} debe tener mensajes nuevos",
            )

        # Verificar actualización de referencias en movimientos revertidos
        recent_notes = self.env["account.move"].search(
            [("journal_id", "=", self.sale_journal.id), ("move_type", "in", ["out_invoice", "out_refund"])],
            order="create_date desc",
            limit=len(non_zero_lines),
        )

        if recent_notes:
            for note in recent_notes:
                reversed_moves = note.exchange_reversed_move_ids
                if reversed_moves:
                    for reversed_move in reversed_moves:
                        self.assertEqual(reversed_move.ref, note.name, "Ref del movimiento revertido debe actualizarse")

    def test_07_zero_balance_warning_behavior(self):
        """Test 07 - Confirms zero-balance partners show warning and skip invoice creation."""
        exchange_entries = self._get_unprocessed_exchange_entries()
        if not exchange_entries:
            self.skipTest("No hay entradas para probar")

        wizard = self._create_wizard_for_entries(exchange_entries)

        # Buscar líneas con balance cero y verificar advertencia
        zero_balance_lines = wizard.line_ids.filtered(lambda l: l.balance == 0.0)

        for line in zero_balance_lines:
            line._compute_show_warning()
            self.assertIn(
                'class="fa fa-exclamation-triangle text-warning"',
                line.show_warning,
                "Debe mostrar advertencia para balance cero",
            )

        # Si ejecutamos el wizard, no debe crear facturas para balances cero
        action = wizard.action_create_debit_credit_notes()
        if action and isinstance(action, dict) and action.get("domain"):
            created_notes = self.env["account.move"].search(action["domain"])
            non_zero_lines = wizard.line_ids.filtered(lambda l: l.balance != 0)

            self.assertEqual(
                len(created_notes), len(non_zero_lines), "Debe crear una nota por partner con balance != 0"
            )

    # ==================== TESTS DE CONFIGURACIÓN Y EDGE CASES ====================

    def test_08_company_exchange_product_validation(self):
        """Test 08 - Tests behavior when exchange difference product is not configured."""
        # Verificar que está configurado inicialmente
        self.assertTrue(
            self.company.exchange_difference_product, "Producto de diferencia de cambio debe estar configurado"
        )

        # Test sin producto configurado
        original_product = self.company.exchange_difference_product
        self.company.exchange_difference_product = False

        with self.assertRaises(UserError):
            self.env["account.exchange.difference.wizard"].with_context(move_line_ids=[]).default_get(["line_ids"])

        # Restaurar configuración
        self.company.exchange_difference_product = original_product

    def test_09_wizard_edge_cases(self):
        """Test 09 - Validates wizard edge cases and already processed entries handling."""
        # Test con entradas ya procesadas
        all_entries = self.env["account.move.line"].search(
            [
                ("journal_id", "=", self.exchange_journal.id),
                ("account_type", "=", "asset_receivable"),
                ("move_type", "=", "entry"),
            ]
        )

        # Marcar algunas como procesadas
        if all_entries:
            processed_entries = all_entries[:1]
            test_move = processed_entries.mapped("move_id")[0]
            # Crear un movimiento de reversión ficticio
            # Ensure the reversal move is balanced
            reversal = self.env["account.move"].create(
                {
                    "journal_id": self.exchange_journal.id,
                    "move_type": "entry",
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": processed_entries.account_id.id,
                                "partner_id": processed_entries.partner_id.id,
                                "debit": abs(processed_entries.balance),
                                "credit": abs(processed_entries.balance),
                            },
                        )
                    ],
                }
            )
            test_move.exchange_reversal_id = reversal.id

            # Ahora test que no se incluyen en wizard
            unprocessed = self._get_unprocessed_exchange_entries()
            self.assertNotIn(processed_entries, unprocessed, "Entradas procesadas no deben aparecer")

    def test_10_invoice_creation_with_taxes(self):
        """Test 10 - Tests invoice creation with taxes when fiscal position mapping applies."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)
        if not exchange_entries:
            self.skipTest("No hay entradas para probar")

        partner = exchange_entries[0].partner_id

        # Buscar posición fiscal con impuestos
        fiscal_position_with_taxes = self.env["account.fiscal.position"].search(
            [("company_id", "=", self.company.id), ("tax_ids", "!=", False)], limit=1
        )

        if fiscal_position_with_taxes:
            wizard = (
                self.env["account.exchange.difference.wizard"]
                .with_context(move_line_ids=exchange_entries.ids)
                .create(
                    {
                        "journal_id": self.sale_journal.id,
                        "fiscal_position": "manual",
                        "fiscal_position_id": fiscal_position_with_taxes.id,
                    }
                )
            )

            action = wizard.action_create_debit_credit_notes()

            if action and action.get("domain"):
                created_notes = self.env["account.move"].search(action["domain"])
                for note in created_notes:
                    self.assertEqual(note.fiscal_position_id, fiscal_position_with_taxes)
                    # Verificar que se aplicaron los mapeos de impuestos si los hay
                    for line in note.invoice_line_ids:
                        mapped_taxes = fiscal_position_with_taxes.map_tax(line.product_id.taxes_id, partner=partner)
                        if mapped_taxes:
                            self.assertTrue(line.tax_ids & mapped_taxes, "Debe aplicar impuestos mapeados")
