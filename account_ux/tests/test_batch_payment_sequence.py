import odoo.tests.common as common


class TestBatchPaymentSequence(common.TransactionCase):
    """The communication of a batch payment must not depend on the sequence being already set."""

    def test_communication_without_sequence(self):
        company = self.env.company.sudo()
        company.batch_payment_sequence_id = False

        communication = company.get_next_batch_payment_communication()

        self.assertTrue(company.batch_payment_sequence_id, "the sequence should have been created")
        self.assertTrue(communication.startswith("BATCH/"), "got %s" % communication)

    def test_communication_keeps_existing_sequence(self):
        company = self.env.company.sudo()
        sequence = company._create_batch_payment_sequence()
        company.batch_payment_sequence_id = sequence

        company.get_next_batch_payment_communication()

        self.assertEqual(company.batch_payment_sequence_id, sequence, "the sequence was replaced")
