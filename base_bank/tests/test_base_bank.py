from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBaseBank(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env["res.bank"].create({"name": "Test Bank", "bic": "testbic"})
        cls.partner = cls.env["res.partner"].create({"name": "Cliente con cuenta"})

    def test_bank_bic_upper_and_search(self):
        self.assertEqual(self.bank.bic, "TESTBIC")
        self.assertEqual(self.bank.display_name, "Test Bank - TESTBIC")
        self.assertEqual(self.env["res.bank"].search([("display_name", "ilike", "testbic")]), self.bank)

    def test_partner_bank_account_form(self):
        with Form(self.env["res.partner.bank"].with_context(default_partner_id=self.partner.id)) as account_form:
            account_form.account_number = "0050001234567890123456"
            account_form.bank_id = self.bank
        account = account_form.save()
        self.assertEqual(account.bank_id, self.bank)
        self.assertEqual(account.bank_name, "Test Bank")

    def test_partner_bank_account_takes_bank_data(self):
        account = self.env["res.partner.bank"].create(
            {"partner_id": self.partner.id, "account_number": "0050001234567890123456", "bank_id": self.bank.id}
        )
        self.assertEqual((account.bank_name, account.bank_bic), ("Test Bank", "TESTBIC"))
        other = self.env["res.partner.bank"].create(
            {
                "partner_id": self.partner.id,
                "account_number": "0050009999999999999999",
                "bank_id": self.bank.id,
                "bank_name": "Given by hand",
            }
        )
        self.assertEqual(other.bank_name, "Given by hand")
        self.assertEqual(other.bank_bic, "TESTBIC")
        self.bank.write({"name": "Other Name", "bic": "otherbic"})
        self.assertEqual((account.bank_name, account.bank_bic), ("Other Name", "OTHERBIC"))
        other.bank_id = False
        self.assertFalse(other.bank_name or other.bank_bic)
        account.bank_name = "Edited by hand"
        self.assertEqual(account.bank_name, "Edited by hand")

    def test_journal_bank(self):
        journal = self.env["account.journal"].create({"name": "Banco Test", "type": "bank", "code": "BTST"})
        journal.bank_account_number = "0050001111111111111111"
        journal.bank_id = self.bank
        self.assertEqual(journal.bank_account_id.bank_id, self.bank)
