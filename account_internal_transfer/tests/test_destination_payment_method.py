# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDestinationPaymentMethod(AccountTestInvoicingCommon):
    """The user picks the payment method line of the destination journal.

    Without it the paired payment always lands on the first available line, so a destination
    journal with two inbound lines has its second outstanding account unreachable.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source_journal = cls.company_data["default_journal_bank"]
        cls.second_outstanding_account = cls.copy_account(cls.inbound_payment_method_line.payment_account_id)
        cls.destination_journal = cls.env["account.journal"].create(
            {
                "name": "Destination Bank",
                "code": "DSTIT",
                "type": "bank",
                "company_id": cls.company_data["company"].id,
            }
        )
        # the auto created inbound line keeps the journal default, the second one gets its own
        # outstanding account: that is the one that is out of reach today
        cls.first_destination_line = cls.destination_journal.inbound_payment_method_line_ids[0]
        cls.first_destination_line.payment_account_id = cls.inbound_payment_method_line.payment_account_id
        cls.second_destination_line = cls.env["account.payment.method.line"].create(
            {
                "name": "Manual Pending",
                "payment_method_id": cls.first_destination_line.payment_method_id.id,
                "payment_account_id": cls.second_outstanding_account.id,
                "journal_id": cls.destination_journal.id,
            }
        )

    def _create_transfer(self, destination_line=None):
        values = {
            "payment_type": "outbound",
            "is_internal_transfer": True,
            "amount": 100.0,
            "journal_id": self.source_journal.id,
            "destination_journal_id": self.destination_journal.id,
            "payment_method_line_id": self.outbound_payment_method_line.id,
        }
        if destination_line:
            values["destination_payment_method_line_id"] = destination_line.id
        return self.env["account.payment"].create(values)

    def test_default_is_the_first_available_line(self):
        """Leaving the field untouched has to reproduce the previous behaviour."""
        payment = self._create_transfer()

        self.assertEqual(
            payment.destination_payment_method_line_id,
            self.destination_journal._get_available_payment_method_lines("inbound")[:1],
            "The default has to be the first available line of the destination journal.",
        )

    def test_available_lines_belong_to_the_destination_journal(self):
        payment = self._create_transfer()

        self.assertIn(self.second_destination_line, payment.available_destination_payment_method_line_ids)
        self.assertNotIn(
            self.inbound_payment_method_line,
            payment.available_destination_payment_method_line_ids,
            "Lines of another journal must not be offered.",
        )

    def test_paired_payment_uses_the_chosen_line(self):
        """The whole point: the second outstanding account becomes reachable."""
        payment = self._create_transfer(destination_line=self.second_destination_line)

        payment.action_post()

        paired_payment = payment.paired_internal_transfer_payment_id
        self.assertEqual(paired_payment.payment_method_line_id, self.second_destination_line)
        self.assertIn(
            self.second_outstanding_account,
            paired_payment.move_id.line_ids.mapped("account_id"),
            "The paired entry has to use the outstanding account of the chosen line.",
        )

    def test_paired_payment_without_choice_keeps_the_default_line(self):
        payment = self._create_transfer()
        default_line = payment.destination_payment_method_line_id

        payment.action_post()

        self.assertEqual(payment.paired_internal_transfer_payment_id.payment_method_line_id, default_line)

    def test_changing_the_destination_journal_recomputes_the_line(self):
        payment = self._create_transfer(destination_line=self.second_destination_line)
        other_journal = self.env["account.journal"].create(
            {
                "name": "Other Destination",
                "code": "OTHIT",
                "type": "bank",
                "company_id": self.company_data["company"].id,
            }
        )
        other_journal.inbound_payment_method_line_ids[
            0
        ].payment_account_id = self.inbound_payment_method_line.payment_account_id

        payment.destination_journal_id = other_journal

        self.assertEqual(
            payment.destination_payment_method_line_id,
            other_journal._get_available_payment_method_lines("inbound")[:1],
            "A line of the previous destination journal must not survive the change.",
        )

    def test_the_context_hook_does_not_override_an_explicit_choice(self):
        payment = self._create_transfer(destination_line=self.second_destination_line)

        payment.with_context(default_payment_method_line_id=self.first_destination_line.id).action_post()

        self.assertEqual(
            payment.paired_internal_transfer_payment_id.payment_method_line_id,
            self.second_destination_line,
            "The explicit choice wins over the context hook.",
        )
