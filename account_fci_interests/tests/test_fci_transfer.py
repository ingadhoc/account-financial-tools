##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.tests.common import TransactionCase


class TestFCITransfer(TransactionCase):
    def setUp(self):
        super().setUp()
        company = self.env.company

        self.fci_income_account = self.env["account.account"].create(
            {
                "name": "FCI Interest Income",
                "code": "FCI.INC.001",
                "account_type": "income",
                "company_ids": [company.id],
            }
        )

        self.bank_journal = self.env["account.journal"].create(
            {
                "name": "Test Bank",
                "code": "BANK",
                "type": "bank",
                "company_id": company.id,
            }
        )
        # Ensure the bank journal has payment accounts configured for internal transfers
        self.bank_journal.outbound_payment_method_line_ids.payment_account_id = self.bank_journal.default_account_id
        self.bank_journal.inbound_payment_method_line_ids.payment_account_id = self.bank_journal.default_account_id

        self.fci_journal = self.env["account.journal"].create(
            {
                "name": "Test FCI Fund",
                "code": "FCI",
                "type": "cash",
                "company_id": company.id,
                "is_fci_journal": True,
                "fci_income_account_id": self.fci_income_account.id,
            }
        )
        # The outstanding account is required on payment method lines for internal transfers
        # Use the journal's own default account (created automatically with the journal)
        self.fci_journal.outbound_payment_method_line_ids.payment_account_id = self.fci_journal.default_account_id

        self.fci_journal.inbound_payment_method_line_ids.payment_account_id = self.fci_journal.default_account_id

    def _create_transfer(self, from_journal, to_journal, amount, interest=0.0):
        """Helper: create and post an internal transfer between two journals."""
        payment = self.env["account.payment"].create(
            {
                "journal_id": from_journal.id,
                "destination_journal_id": to_journal.id,
                "is_internal_transfer": True,
                "payment_type": "outbound",
                "partner_id": self.env.company.partner_id.id,
                "amount": amount,
                "fci_interest_amount": interest,
                "payment_method_line_id": from_journal.outbound_payment_method_line_ids[:1].id,
            }
        )
        payment.action_post()
        return payment

    def test_inbound_to_fci_no_interest_lines(self):
        """
        Transfer FROM bank TO fci_journal (destination_journal_id = fci_journal).

        The interest line must NOT appear in either move:
          - move_id of the original payment (bank → FCI)
          - move_id of the paired payment generated after posting
        """
        amount = 500_000.0
        payment = self._create_transfer(
            from_journal=self.bank_journal,
            to_journal=self.fci_journal,
            amount=amount,
            interest=10000.0,  # interest set, but must be ignored because journal_id is not FCI
        )

        # Original payment move: no interest line
        move = payment.move_id
        self.assertEqual(move.state, "posted")
        interest_lines = move.line_ids.filtered(lambda line: line.account_id == self.fci_income_account)
        self.assertFalse(interest_lines, "No interest line expected on the inbound-to-FCI move")

        # Paired payment move: no interest line either
        paired = payment.paired_internal_transfer_payment_id
        self.assertTrue(paired, "A paired payment must exist after posting")
        paired_interest_lines = paired.move_id.line_ids.filtered(
            lambda line: line.account_id == self.fci_income_account
        )
        self.assertFalse(
            paired_interest_lines,
            "No interest line expected on the paired payment move",
        )

    def test_outbound_from_fci_interest_line(self):
        """
        Transfer FROM fci_journal TO bank (journal_id = fci_journal, outbound).

        Expected move on the FCI payment (journal_id.is_fci_journal = True):
          - 3 lines total
          - Debit  = amount          (liquidity line, FCI account)
          - Credit = amount - interest  (counterpart — capital returned)
          - Credit = interest           (fci_income_account_id — accrued interest)
          - Move is balanced

        The paired payment (bank side) must NOT have an interest line.
        """
        amount = 1000000.0
        interest = 15000.0
        capital = amount + interest  # 1,015,000

        payment = self._create_transfer(
            from_journal=self.fci_journal,
            to_journal=self.bank_journal,
            amount=amount,
            interest=interest,
        )

        # --- Original FCI payment move ---
        move = payment.move_id
        self.assertEqual(move.state, "posted")
        self.assertEqual(len(move.line_ids), 3, "FCI move must have exactly 3 lines")

        interest_line = move.line_ids.filtered(lambda line: line.account_id == self.fci_income_account)
        self.assertEqual(len(interest_line), 1, "Exactly one interest line expected")
        self.assertAlmostEqual(interest_line.credit, interest, places=2)
        self.assertAlmostEqual(interest_line.debit, 0.0, places=2)

        journal_account_line = move.line_ids.filtered(
            lambda line: line.account_id == payment.journal_id.default_account_id
        )

        counterpart_line = move.line_ids.filtered(
            lambda line: (
                line.account_id != self.fci_income_account and line.account_id != payment.journal_id.default_account_id
            )
        )
        self.assertAlmostEqual(journal_account_line.credit, amount, places=2)
        self.assertAlmostEqual(counterpart_line.debit, capital, places=2)

        total_debit = sum(move.line_ids.mapped("debit"))
        total_credit = sum(move.line_ids.mapped("credit"))
        self.assertAlmostEqual(total_debit, total_credit, places=2)

        # --- Paired payment move (bank side) must NOT have interest line ---
        paired = payment.paired_internal_transfer_payment_id
        self.assertTrue(paired, "A paired payment must exist after posting")
        paired_interest_lines = paired.move_id.line_ids.filtered(
            lambda line: line.account_id == self.fci_income_account
        )
        self.assertFalse(
            paired_interest_lines,
            "No interest line expected on the paired (bank) payment move",
        )
        self.assertAlmostEqual(
            paired.amount,
            capital,
            places=2,
            msg="Paired payment amount must equal capital (amount + interest)",
        )
