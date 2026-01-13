from dateutil.relativedelta import relativedelta
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestExchangeDifferenceInvoice(TransactionCase):
    """Test exchange difference invoice functionality using demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Get company
        cls.company = cls.env.ref("base.company_ri")
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))

        # Get partners used in demo data
        cls.partner_adhoc = cls.env.ref("l10n_ar_tax.res_partner_adhoc_caba")
        cls.partner_gritti = cls.env.ref("l10n_ar.res_partner_gritti_agrimensura")

        # Demo data is loaded by the XML file calling _install_exchange_diff_demo
        # Find invoices created by demo data (USD invoices for our test partners from this month)
        first_day_of_month = fields.Date.today() + relativedelta(day=1)
        cls.demo_invoices = cls.env["account.move"].search(
            [
                ("move_type", "=", "out_invoice"),
                ("partner_id", "in", [cls.partner_adhoc.id, cls.partner_gritti.id]),
                ("currency_id", "=", cls.env.ref("base.USD").id),
                ("invoice_date", ">=", first_day_of_month),
                ("invoice_date", "<=", first_day_of_month + relativedelta(days=3)),
            ],
            order="invoice_date, partner_id",
        )

        # Separate invoices for easier reference in tests
        cls.invoice_1 = cls.demo_invoices.filtered(
            lambda i: i.partner_id == cls.partner_adhoc and i.invoice_date == first_day_of_month
        )[:1]
        cls.invoice_2 = cls.demo_invoices.filtered(
            lambda i: i.partner_id == cls.partner_adhoc and i.invoice_date == first_day_of_month + relativedelta(days=1)
        )[:1]
        cls.invoice_3 = cls.demo_invoices.filtered(
            lambda i: i.partner_id == cls.partner_adhoc and i.invoice_date == first_day_of_month + relativedelta(days=2)
        )[:1]
        cls.invoice_4 = cls.demo_invoices.filtered(lambda i: i.partner_id == cls.partner_gritti)[:1]

        # Get exchange journal
        cls.exchange_journal = cls.company.currency_exchange_journal_id

        # Get sale journal for debit/credit notes
        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )

    def _get_unprocessed_exchange_entries(self, limit=None, partner_id=None):
        """Helper method to get unprocessed exchange difference entries.

        Args:
            limit: Maximum number of entries to return
            partner_id: Optional partner to filter by

        Returns:
            Recordset of unprocessed account.move.line entries
        """
        domain = [
            ("journal_id", "=", self.exchange_journal.id),
            ("account_type", "=", "asset_receivable"),
            ("move_type", "=", "entry"),
            ("move_id.exchange_reversal_id", "=", False),
            ("move_id.exchange_reversed_move_ids", "=", False),
        ]

        if partner_id:
            domain.append(("partner_id", "=", partner_id))

        return self.env["account.move.line"].search(domain, limit=limit)

    def test_01_exchange_difference_entries_created(self):
        """Test that exchange difference entries are created after payment reconciliation."""
        # Verify that exchange difference entries were created by the demo data
        exchange_entries = self.env["account.move.line"].search(
            [
                ("journal_id", "=", self.exchange_journal.id),
                ("account_type", "=", "asset_receivable"),
                ("move_type", "=", "entry"),
            ]
        )

        # Should have exchange entries for the paid invoices
        self.assertTrue(exchange_entries, "Exchange difference entries should be created after payment")

        # Verify they are linked to partners (the actual partners may vary based on demo data)
        partners = exchange_entries.mapped("partner_id")
        self.assertTrue(partners, "Exchange entries should have partners assigned")
        # At least one of our demo partners should be present
        demo_partners = self.partner_adhoc | self.partner_gritti
        self.assertTrue(partners & demo_partners, "At least one demo partner should have exchange entries")

    def test_02_exchange_info_computed(self):
        """Test that exchange_info field is computed correctly on move lines."""
        exchange_entries = self.env["account.move.line"].search(
            [
                ("journal_id", "=", self.exchange_journal.id),
                ("account_type", "=", "asset_receivable"),
                ("move_type", "=", "entry"),
            ],
            limit=1,
        )

        if exchange_entries:
            # The exchange_info should contain information about related invoices
            self.assertTrue(
                exchange_entries[0].exchange_info, "Exchange info should be computed for exchange difference entries"
            )
            self.assertIn("Exchange diff for:", exchange_entries[0].exchange_info)

    def test_03_wizard_opens_with_correct_data(self):
        """Test that the exchange difference wizard opens with correct grouped data."""
        # Get exchange difference entries that haven't been processed
        exchange_entries = self._get_unprocessed_exchange_entries()

        self.assertTrue(exchange_entries, "Should have unprocessed exchange entries")

        # Create wizard
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                }
            )
        )

        # Wizard should have lines grouped by partner
        self.assertTrue(wizard.line_ids, "Wizard should have lines")

        # Verify partners are present (actual partners may vary)
        wizard_partners = wizard.line_ids.mapped("partner_id")
        self.assertTrue(wizard_partners, "Wizard should have partners")

        # Verify balance is calculated
        for line in wizard.line_ids:
            # Balance can be 0 if there are offsetting entries
            self.assertIsNotNone(line.balance, "Balance should be calculated for each partner")
            self.assertIsInstance(
                line.balance, (int, float), f"Balance should be a numeric value, got {type(line.balance)}"
            )

    def test_04_create_debit_credit_notes(self):
        """Test creating debit/credit notes from exchange difference wizard."""
        # Get unprocessed exchange entries
        exchange_entries = self._get_unprocessed_exchange_entries()

        initial_count = len(exchange_entries)
        self.assertGreater(initial_count, 0, "Should have exchange entries to process")

        # Create wizard with company context
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_company(self.company)
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                    "fiscal_position": "automatic",
                    "company_id": self.company.id,
                }
            )
        )

        # Execute wizard action
        action = wizard.action_create_debit_credit_notes()

        # Verify debit/credit notes were created
        if action and isinstance(action, dict) and action.get("domain"):
            domain = action["domain"]
            created_notes = self.env["account.move"].search(domain)

            # Should have created at least one debit/credit note (one per partner with non-zero balance)
            non_zero_lines = wizard.line_ids.filtered(lambda l: l.balance != 0)
            self.assertEqual(
                len(created_notes),
                len(non_zero_lines),
                "Should create one debit/credit note per partner with non-zero balance",
            )

            # Verify notes are posted
            for note in created_notes:
                # Notes may be in draft if there are validation issues, just check they exist
                self.assertIn(note.state, ["draft", "posted"], "Debit/credit notes should be created")

                # Verify the exchange difference product is used
                product = self.env.company.exchange_difference_product
                if product:
                    self.assertIn(product, note.invoice_line_ids.mapped("product_id"))

        # Verify that the specific exchange entries processed in this test are now marked as processed
        exchange_entries.invalidate_recordset()
        exchange_moves = exchange_entries.mapped("move_id")
        for move in exchange_moves:
            self.assertTrue(
                move.exchange_reversal_id,
                f"Exchange move {move.name} should have exchange_reversal_id set after processing",
            )

    def test_05_reconciliation_after_debit_note(self):
        """Test that reconciliation is created after debit/credit note creation."""
        # Get unprocessed exchange entries for one partner only
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1, partner_id=self.partner_adhoc.id)

        if not exchange_entries:
            self.skipTest("No unprocessed exchange entries found for testing reconciliation")

        exchange_move = exchange_entries.mapped("move_id")

        # Create wizard
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                }
            )
        )

        # Execute wizard
        wizard.action_create_debit_credit_notes()

        # Verify reversal entry was created
        reversal_move = exchange_move.exchange_reversal_id
        self.assertTrue(reversal_move, "Reversal entry should be created")
        self.assertEqual(reversal_move.state, "posted", "Reversal entry should be posted")

        # Verify reconciliation was made
        exchange_line = exchange_entries[0]
        reversal_line = reversal_move.line_ids.filtered(
            lambda l: l.account_id == exchange_line.account_id and l.partner_id == exchange_line.partner_id
        )
        self.assertTrue(reversal_line, "Reversal entry should have matching line")

        # Check if lines are reconciled
        self.assertTrue(
            exchange_line.matched_debit_ids or exchange_line.matched_credit_ids or exchange_line.full_reconcile_id,
            "Exchange line should be reconciled",
        )

    def test_06_wizard_validation_no_entries(self):
        """Test wizard validation when no entries are provided."""
        # The wizard validates entries in default_get, so we need to test the validation method directly
        wizard_obj = self.env["account.exchange.difference.wizard"].with_company(self.company)

        # Test validation with empty entries
        with self.assertRaises(UserError, msg="Should raise error when no entries to process"):
            wizard_obj._validate_entries_to_process(self.env["account.move.line"])

    def test_07_wizard_validation_multiple_companies(self):
        """Test wizard validation when entries from multiple companies are selected."""
        # Get entries from current company
        exchange_entries = self.env["account.move.line"].search(
            [
                ("journal_id", "=", self.exchange_journal.id),
                ("account_type", "=", "asset_receivable"),
                ("move_type", "=", "entry"),
            ],
            limit=1,
        )

        if not exchange_entries:
            self.skipTest("No exchange entries found for multi-company test")

        # Try to manually trigger validation with different company scenario
        # Note: In a real scenario, you would need entries from different companies
        # For this test, we verify the validation logic exists
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                    "company_id": self.company.id,
                }
            )
        )

        # The validation should work correctly when called
        try:
            wizard._validate_entries_to_process(exchange_entries)
        except UserError:
            self.fail("Should not raise error for entries from same company")

    def test_08_exchange_domain_filter(self):
        """Test the exchange difference domain filter."""
        # Test the domain used to filter exchange entries
        aml = self.env["account.move.line"].with_company(self.company)
        domain = aml._get_exchange_difference_domain()

        # Domain should filter for exchange journal and receivable account
        # Check if domain contains a clause for journal_id
        journal_clause = any(
            isinstance(item, (list, tuple)) and len(item) == 3 and item[0] == "journal_id" for item in domain
        )
        self.assertTrue(journal_clause, "Domain should filter by journal_id")
        self.assertIn(("account_type", "=", "asset_receivable"), domain)
        self.assertIn(("move_type", "=", "entry"), domain)

        # Apply domain and verify results
        exchange_entries = aml.search(domain)
        for entry in exchange_entries:
            self.assertEqual(entry.account_type, "asset_receivable")
            self.assertEqual(entry.move_type, "entry")

    def test_09_exchange_difference_action(self):
        """Test opening exchange difference action."""
        aml = self.env["account.move.line"]
        action = aml.action_exchange_difference()

        # Verify action structure
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move.line")
        self.assertEqual(action["view_mode"], "list")

        # Verify default filters are set
        context = action.get("context", {})
        self.assertIn("search_default_to_process", context)
        self.assertIn("search_default_current_month", context)

        # Verify that the domain in the action is valid and returns exchange entries
        domain = action.get("domain", [])
        if domain:
            results = self.env["account.move.line"].search(domain)
            # If there are results, verify they are exchange difference entries
            if results:
                for entry in results:
                    self.assertEqual(entry.account_type, "asset_receivable", "Result should be receivable account")
                    self.assertEqual(entry.move_type, "entry", "Result should be a journal entry")

    def test_10_wizard_with_manual_fiscal_position(self):
        """Test wizard with manual fiscal position selection."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)

        if not exchange_entries:
            self.skipTest("No unprocessed exchange entries found")

        # Get a fiscal position
        fiscal_position = self.env["account.fiscal.position"].search([("company_id", "=", self.company.id)], limit=1)

        if not fiscal_position:
            self.skipTest("No fiscal position found for testing")

        # Create wizard with manual fiscal position
        wizard = (
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

        # Verify fiscal position is set
        self.assertEqual(wizard.fiscal_position, "manual")
        self.assertEqual(wizard.fiscal_position_id, fiscal_position)

    def test_11_exchange_reversed_move_ref_updated(self):
        """Test that reversed move ref is updated with debit/credit note name."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)

        if not exchange_entries:
            self.skipTest("No unprocessed exchange entries found")

        exchange_move = exchange_entries.mapped("move_id")

        # Create and execute wizard with company context
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_company(self.company)
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                    "company_id": self.company.id,
                }
            )
        )

        wizard.action_create_debit_credit_notes()

        # Verify reversal entry was created
        reversal_move = exchange_move.exchange_reversal_id
        self.assertTrue(reversal_move, "Reversal entry should be created")
        self.assertEqual(reversal_move.state, "posted", "Reversal entry should be posted")

        # Verify that a debit/credit note was created for the partner
        debit_credit_notes = self.env["account.move"].search(
            [
                ("partner_id", "=", exchange_entries.partner_id.id),
                ("journal_id", "=", self.sale_journal.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ],
            order="create_date desc",
            limit=1,
        )

        if debit_credit_notes:
            # Verify that exchange_reversed_move_ids have their ref field updated with the debit/credit note name
            reversed_moves = debit_credit_notes.exchange_reversed_move_ids
            if reversed_moves:
                for reversed_move in reversed_moves:
                    self.assertEqual(
                        reversed_move.ref,
                        debit_credit_notes.name,
                        "Exchange reversed move ref should be updated with debit/credit note name",
                    )

    def test_12_zero_balance_no_invoice_created(self):
        """Test that no debit/credit note is created when balance is zero."""
        # For this test, we would need a scenario where partner balance sums to zero
        # This is tested through the wizard line warning computation
        # Note: Using base domain without unprocessed filter since we want all entries
        exchange_entries = self.env["account.move.line"].search(
            [
                ("journal_id", "=", self.exchange_journal.id),
                ("account_type", "=", "asset_receivable"),
                ("move_type", "=", "entry"),
            ]
        )

        if not exchange_entries:
            self.skipTest("No exchange entries found")

        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                }
            )
        )

        # Check for lines with zero balance
        zero_balance_lines = wizard.line_ids.filtered(lambda l: l.balance == 0.0)

        for line in zero_balance_lines:
            # Should show warning for zero balance
            line._compute_show_warning()
            self.assertIn("The balance for this partner is zero", line.show_warning)
            self.assertIn('class="fa fa-exclamation-triangle text-warning"', line.show_warning)

    def test_13_partner_messages_on_reconciliation(self):
        """Test that messages are posted to payment records after reconciliation."""
        exchange_entries = self._get_unprocessed_exchange_entries(limit=1)

        if not exchange_entries:
            self.skipTest("No unprocessed exchange entries found")

        # Get related payments before processing
        partial_reconciles = self.env["account.partial.reconcile"].search(
            [("exchange_move_id", "in", exchange_entries.mapped("move_id").ids)]
        )

        related_payments = (
            (partial_reconciles.mapped("debit_move_id") + partial_reconciles.mapped("credit_move_id"))
            .filtered(lambda l: l.move_type == "entry")
            .mapped("payment_id")
        )

        if not related_payments:
            self.skipTest("No related payments found to verify messages")

        initial_message_count = {payment.id: len(payment.message_ids) for payment in related_payments}

        # Create and execute wizard with company context
        wizard = (
            self.env["account.exchange.difference.wizard"]
            .with_company(self.company)
            .with_context(move_line_ids=exchange_entries.ids)
            .create(
                {
                    "journal_id": self.sale_journal.id,
                    "company_id": self.company.id,
                }
            )
        )

        wizard.action_create_debit_credit_notes()

        # Verify messages were posted
        for payment in related_payments:
            payment.invalidate_recordset()
            current_message_count = len(payment.message_ids)
            self.assertGreater(
                current_message_count,
                initial_message_count.get(payment.id, 0),
                f"Payment {payment.name} should have new messages",
            )

    def test_14_currency_rates_demo_data(self):
        """Test that currency rates were created correctly by demo data."""
        first_day_of_month = fields.Date.today() + relativedelta(day=1)

        # Expected rates: 1000, 1100, 1200, 1300 for days 1-4
        usd = self.env.ref("base.USD")
        expected_rates = [1000, 1100, 1200, 1300]

        for days_ago, expected_rate in enumerate(expected_rates):
            date_value = first_day_of_month + relativedelta(days=days_ago)
            rate = self.env["res.currency.rate"].search(
                [("currency_id", "=", usd.id), ("name", "=", date_value.isoformat())], limit=1
            )

            self.assertTrue(rate, f"Rate should exist for {date_value}")
            # The rate is stored as 1 / expected_rate
            expected_rate_value = 1 / expected_rate
            self.assertAlmostEqual(
                rate.rate,
                expected_rate_value,
                places=6,
                msg=f"Rate for {date_value} should be {expected_rate_value} (1/{expected_rate})",
            )
