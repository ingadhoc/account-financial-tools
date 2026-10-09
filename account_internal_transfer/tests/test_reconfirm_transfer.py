# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestReconfirmTransfer(AccountTestInvoicingCommon):
    """A transfer reset to draft and confirmed again has to reconcile its transfer lines again.

    Resetting a leg to draft unreconciles the two transfer account lines. The pair already
    exists on the second confirmation, so nothing created it and nothing reconciled it either.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.destination_journal = cls.env["account.journal"].create(
            {
                "name": "Destination Bank",
                "code": "DSTIT",
                "type": "bank",
                "company_id": cls.company_data["company"].id,
            }
        )
        cls.destination_journal.inbound_payment_method_line_ids[
            0
        ].payment_account_id = cls.inbound_payment_method_line.payment_account_id
        cls.payment = cls.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "is_internal_transfer": True,
                "amount": 100.0,
                "journal_id": cls.company_data["default_journal_bank"].id,
                "destination_journal_id": cls.destination_journal.id,
                "payment_method_line_id": cls.outbound_payment_method_line.id,
            }
        )
        cls.payment.action_post()
        cls.paired_payment = cls.payment.paired_internal_transfer_payment_id

    def _transfer_lines(self):
        return (self.payment.move_id + self.paired_payment.move_id).line_ids.filtered(
            lambda l: l.account_id == self.payment.destination_account_id
        )

    def assertPairReconciled(self, msg):
        lines = self._transfer_lines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(lines.mapped("reconciled")), msg)
        self.assertEqual(len(lines.mapped("full_reconcile_id")), 1, "Both lines have to share one full reconcile.")

    def test_first_confirmation_reconciles_the_pair(self):
        self.assertPairReconciled("The first confirmation has to reconcile the pair, as before.")

    def test_reconfirming_one_leg_reconciles_the_pair_again(self):
        self.payment.action_draft()
        self.assertFalse(any(self._transfer_lines().mapped("reconciled")), "Draft unreconciles the pair.")

        self.payment.action_post()

        self.assertEqual(self.payment.paired_internal_transfer_payment_id, self.paired_payment, "No new pair.")
        self.assertPairReconciled("The second confirmation has to reconcile the pair again.")

    def test_reconfirming_the_paired_leg_reconciles_the_pair_again(self):
        self.paired_payment.action_draft()

        self.paired_payment.action_post()

        self.assertPairReconciled("Confirming the paired leg again has to reconcile the pair too.")

    def test_confirming_both_legs_together_reconciles_the_pair(self):
        """From the list, both legs reset to draft and posted in one call."""
        both = self.payment + self.paired_payment
        both.action_draft()
        self.assertFalse(any(self._transfer_lines().mapped("reconciled")))

        both.action_post()

        self.assertPairReconciled("Posting both legs in one batch has to reconcile the pair.")
