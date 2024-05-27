# Copyright 2019 ForgeFlow, S.L.
# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from base64 import b64encode
from decimal import Decimal, ROUND_HALF_UP
from os import path
from unittest.mock import Mock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import common
from odoo.tools import float_round


class TestAccountBankStatementImportTxtXlsx(common.TransactionCase):
    def setUp(self):
        super().setUp()

        self.now = fields.Datetime.now()
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_usd.active = True
        # Make sure the currency of the company is USD, as this not always happens
        # To be removed in V17: https://github.com/odoo/odoo/pull/107113
        self.company = self.env.company
        self.env.cr.execute(
            "UPDATE res_company SET currency_id = %s WHERE id = %s",
            (self.env.ref("base.USD").id, self.company.id),
        )
        # Activate EUR for unit test, by default is not active
        self.currency_eur.active = True
        self.sample_statement_map = self.env.ref(
            "account_statement_import_txt_xlsx.sample_statement_map"
        )
        self.AccountJournal = self.env["account.journal"]
        self.AccountBankStatement = self.env["account.bank.statement"]
        self.AccountStatementImport = self.env["account.statement.import"]
        self.AccountStatementImportSheetMapping = self.env[
            "account.statement.import.sheet.mapping"
        ]

        self.suspense_account = self.env["account.account"].create(
            {
                "code": "987654",
                "name": "Suspense Account",
                "account_type": "asset_current",
            }
        )

        self.parser = self.env["account.statement.import.sheet.parser"]
        # Mock the mapping object to return predefined separators
        self.mock_mapping_comma_dot = Mock()
        self.mock_mapping_comma_dot._get_float_separators.return_value = (",", ".")
        self.mock_mapping_dot_comma = Mock()
        self.mock_mapping_dot_comma._get_float_separators.return_value = (".", ",")


    def _data_file(self, filename, encoding=None):
        mode = "rt" if encoding else "rb"
        with open(path.join(path.dirname(__file__), filename), mode) as file:
            data = file.read()
            if encoding:
                data = data.encode(encoding)
            return b64encode(data)

    def test_import_csv_file(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/sample_statement_en.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/sample_statement_en.csv",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 2)

    def test_import_empty_csv_file(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/empty_statement_en.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/empty_statement_en.csv",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        with self.assertRaises(UserError):
            wizard.with_context(
                account_statement_import_txt_xlsx_test=True
            ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 0)

    def test_import_xlsx_file(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/sample_statement_en.xlsx")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/sample_statement_en.xlsx",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 2)

    def test_import_empty_xlsx_file(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/empty_statement_en.xlsx")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/empty_statement_en.xlsx",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        with self.assertRaises(UserError):
            wizard.with_context(
                account_statement_import_txt_xlsx_test=True
            ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 0)

    def test_original_currency(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/original_currency.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/original_currency.csv",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 1)

        line = statement.line_ids
        self.assertEqual(line.currency_id, self.currency_usd)
        self.assertEqual(line.amount, 1525.0)
        self.assertEqual(line.foreign_currency_id, self.currency_eur)
        line_amount_currency = float_round(line.amount_currency, precision_digits=1)
        self.assertEqual(line_amount_currency, 1000.0)

    def test_original_currency_empty(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        data = self._data_file("fixtures/original_currency_empty.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/original_currency_empty.csv",
                "statement_file": data,
                "sheet_mapping_id": self.sample_statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 1)

        line = statement.line_ids
        self.assertFalse(line.foreign_currency_id)
        self.assertEqual(line.amount_currency, 0.0)

    def test_multi_currency(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {
                "currency_column": "Currency",
                "original_currency_column": None,
                "original_amount_column": None,
            }
        )
        data = self._data_file("fixtures/multi_currency.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/multi_currency.csv",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 1)

        line = statement.line_ids
        self.assertFalse(line.foreign_currency_id)
        self.assertEqual(line.amount, -33.5)

    def test_balance(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {
                "balance_column": "Balance",
                "original_currency_column": None,
                "original_amount_column": None,
            }
        )
        data = self._data_file("fixtures/balance.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/balance.csv",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 2)
        self.assertEqual(statement.balance_start, 10.0)
        self.assertEqual(statement.balance_end_real, 1510.0)
        self.assertEqual(statement.balance_end, 1510.0)

    def test_debit_credit(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {
                "balance_column": "Balance",
                "original_currency_column": None,
                "original_amount_column": None,
                "debit_credit_column": "D/C",
                "debit_value": "D",
                "credit_value": "C",
            }
        )
        data = self._data_file("fixtures/debit_credit.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/debit_credit.csv",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 2)
        self.assertEqual(statement.balance_start, 10.0)
        self.assertEqual(statement.balance_end_real, 1510.0)
        self.assertEqual(statement.balance_end, 1510.0)

    def test_debit_credit_amount(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {   
                "amount_type":"distinct_credit_debit",
                "amount_debit_column": "Debit",
                "amount_credit_column": "Credit",
                "balance_column": "Balance",
                "amount_column": None,
                "original_currency_column": None,
                "original_amount_column": None,
            }
        )
        data = self._data_file("fixtures/debit_credit_amount.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/debit_credit_amount.csv",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            account_statement_import_txt_xlsx_test=True
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 4)
        self.assertEqual(statement.balance_start, 10.0)
        self.assertEqual(statement.balance_end_real, 1510.0)
        self.assertEqual(statement.balance_end, 1510.0)

    def test_metadata_separated_debit_credit_csv(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {
                "footer_lines_count": 1,
                "column_labels_row": 5,
                "amount_column": None,
                "partner_name_column": None,
                "bank_account_column": None,
                "float_thousands_sep": "none",
                "float_decimal_sep": "comma",
                "timestamp_format": "%m/%d/%y",
                "original_currency_column": None,
                "original_amount_column": None,
                "amount_type": "distinct_credit_debit",
                "debit_column": "Debit",
                "credit_column": "Credit",
            }
        )
        data = self._data_file("fixtures/meta_data_separated_credit_debit.csv", "utf-8")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/meta_data_separated_credit_debit.csv",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            journal_id=journal.id,
            account_bank_statement_import_txt_xlsx_test=True,
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 4)
        line1 = statement.line_ids.filtered(lambda x: x.payment_ref == "LABEL 1")
        line4 = statement.line_ids.filtered(lambda x: x.payment_ref == "LABEL 4")
        self.assertEqual(line1.amount, 50)
        self.assertEqual(line4.amount, -1300)

    def test_metadata_separated_debit_credit_xlsx(self):
        journal = self.AccountJournal.create(
            {
                "name": "Bank",
                "type": "bank",
                "code": "BANK",
                "currency_id": self.currency_usd.id,
                "suspense_account_id": self.suspense_account.id,
            }
        )
        statement_map = self.sample_statement_map.copy(
            {
                "footer_lines_count": 1,
                "column_labels_row": 5,
                "amount_column": None,
                "partner_name_column": None,
                "bank_account_column": None,
                "float_thousands_sep": "none",
                "float_decimal_sep": "comma",
                "timestamp_format": "%m/%d/%y",
                "original_currency_column": None,
                "original_amount_column": None,
                "amount_type": "distinct_credit_debit",
                "debit_column": "Debit",
                "credit_column": "Credit",
            }
        )
        data = self._data_file("fixtures/meta_data_separated_credit_debit.xlsx")
        wizard = self.AccountStatementImport.with_context(journal_id=journal.id).create(
            {
                "statement_filename": "fixtures/meta_data_separated_credit_debit.xlsx",
                "statement_file": data,
                "sheet_mapping_id": statement_map.id,
            }
        )
        wizard.with_context(
            journal_id=journal.id,
            account_bank_statement_import_txt_xlsx_test=True,
        ).import_file_button()
        statement = self.AccountBankStatement.search([("journal_id", "=", journal.id)])
        self.assertEqual(len(statement), 1)
        self.assertEqual(len(statement.line_ids), 4)
        line1 = statement.line_ids.filtered(lambda x: x.payment_ref == "LABEL 1")
        line4 = statement.line_ids.filtered(lambda x: x.payment_ref == "LABEL 4")
        self.assertEqual(line1.amount, 50)
        self.assertEqual(line4.amount, -1300)

    def test_parse_decimal(self):
        # Define a series of test cases
        test_cases = [
            ("1,234.56", Decimal('1234.56'), self.mock_mapping_comma_dot),
            ("1,234,567.89", Decimal('1234567.89'), self.mock_mapping_comma_dot),
            ("-1,234.56", Decimal('-1234.56'), self.mock_mapping_comma_dot),
            ("$1,234.56", Decimal('1234.56'), self.mock_mapping_comma_dot),
            ("1,234.56 USD", Decimal('1234.56'), self.mock_mapping_comma_dot),
            ("   1,234.56   ", Decimal('1234.56'), self.mock_mapping_comma_dot),
            ("not a number", Decimal('0'), self.mock_mapping_comma_dot),
            (" ", Decimal('0'), self.mock_mapping_comma_dot),
            ("", Decimal('0'), self.mock_mapping_comma_dot),
            ("USD", Decimal('0'), self.mock_mapping_comma_dot),
            ("12,34.56", Decimal('1234.56'), self.mock_mapping_comma_dot),
            ("1234,567.89", Decimal('1234567.89'), self.mock_mapping_comma_dot),
            ("1234.567,89", Decimal('1234567.89'), self.mock_mapping_dot_comma),
        ]

        for value, expected, mock_mapping in test_cases:
            with self.subTest(value=value):
                result = self.parser._parse_decimal(value, mock_mapping)
                self.assertEqual(result, expected, f"Failed for value: {value}")

    def test_decimal_and_float_inputs(self):
        def round_decimal(value, places=2):
            return value.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)

        # Test direct Decimal and float inputs with rounding
        self.assertEqual(
            round_decimal(self.parser._parse_decimal(-1234.56, self.mock_mapping_comma_dot)),
            Decimal("-1234.56"),
        )
        self.assertEqual(
            round_decimal(self.parser._parse_decimal(1234.56, self.mock_mapping_comma_dot)),
            Decimal("1234.56"),
        )
        self.assertEqual(
            round_decimal(self.parser._parse_decimal(Decimal("-1234.56"), self.mock_mapping_comma_dot)),
            Decimal("-1234.56"),
        )
        self.assertEqual(
            round_decimal(self.parser._parse_decimal(Decimal("1234.56"), self.mock_mapping_comma_dot)),
            Decimal("1234.56"),
        )

