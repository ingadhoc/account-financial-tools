from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
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


class DebtReportCommon(TransactionCase):
    """A partner with its own receivable account, plus helpers to post debt entries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # pin the report to a single company: how many currencies self.env.companies adds
        # up to depends on the database, and it decides whether amounts are unambiguous
        cls.company = cls.env.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.company_currency = cls.company.currency_id
        cls.foreign_currency = cls.env.ref("base.EUR")
        if cls.foreign_currency == cls.company_currency:
            cls.foreign_currency = cls.env.ref("base.USD")
        cls.foreign_currency.active = True
        # drop whatever rates the database already carries for this currency, so the
        # amounts below are deterministic whichever chart or demo data is installed
        cls.env["res.currency.rate"].search(
            [("currency_id", "=", cls.foreign_currency.id), ("company_id", "=", cls.company.id)]
        ).unlink()
        cls._set_foreign_rate("2024-01-01", 2.0)
        cls.partner = cls.env["res.partner"].create({"name": "Debt Report Partner"})
        # reuse the chart's accounts and misc journal: creating them needs required
        # fields that other installed modules add, and those vary from build to build.
        # The partner is brand new, so nothing else lands on its ledger anyway.
        cls.receivable_account = cls.partner.with_company(cls.company).property_account_receivable_id
        cls.counterpart_account = cls.env["account.account"].search(
            [("account_type", "not in", ("asset_receivable", "liability_payable"))], limit=1
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        assert (
            cls.receivable_account and cls.counterpart_account and cls.journal
        ), "the database needs a chart of accounts installed to run these tests"

    @classmethod
    def _set_foreign_rate(cls, date, rate):
        return cls.env["res.currency.rate"].create(
            {
                "name": date,
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
                "rate": rate,
            }
        )

    @classmethod
    def _create_debt_move(cls, balance, amount_currency=None, currency=None, date="2024-06-15"):
        """Post an entry with a single receivable line for the test partner."""
        currency = currency or cls.company_currency
        if amount_currency is None:
            amount_currency = balance
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": cls.journal.id,
                "date": date,
                "currency_id": currency.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": "debt",
                            "account_id": cls.receivable_account.id,
                            "partner_id": cls.partner.id,
                            # on entries the currency lives on the line, the one on the
                            # move only drives invoices (_compute_currency_id)
                            "currency_id": currency.id,
                            "balance": balance,
                            "amount_currency": amount_currency,
                        }
                    ),
                    Command.create(
                        {
                            "name": "debt counterpart",
                            "account_id": cls.counterpart_account.id,
                            "currency_id": currency.id,
                            "balance": -balance,
                            "amount_currency": -amount_currency,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move

    @classmethod
    def _receivable_line(cls, move):
        return move.line_ids.filtered(lambda line: line.account_id == cls.receivable_account)

    def _report_lines(self, historical_full=True, **context):
        return self.partner.with_context(historical_full=historical_full, **context)._get_debt_report_lines()

    def _report_move_names(self, **currency_flags):
        """Names of the moves that made it into the report for the given flags."""
        return [line["name"] for line in self._report_lines(**currency_flags)]


class TestDebtReportCurrencyMode(DebtReportCommon):
    """The currency checks of the wizard filter which items get into the report.

    Ticking only one of them narrows the report down to the items issued in that
    currency; ticking both (or neither, when the report is rendered without these
    context keys) gives the consolidated report with every item.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 100 in company currency, and 100 of the foreign currency (50 at rate 2.0)
        cls.local_move = cls._create_debt_move(100.0)
        cls.foreign_move = cls._create_debt_move(50.0, amount_currency=100.0, currency=cls.foreign_currency)

    def test_currency_mode_matrix(self):
        """Both ticked and none ticked mean the same thing: no filtering."""
        cases = [
            ({"company_currency": True, "secondary_currency": True}, False),
            ({"company_currency": True, "secondary_currency": False}, "company"),
            ({"company_currency": True}, "company"),
            ({"company_currency": False, "secondary_currency": True}, "secondary"),
            ({"secondary_currency": True}, "secondary"),
            ({"company_currency": False, "secondary_currency": False}, False),
            ({}, False),
            # the context the distributor portal renders the report with
            ({"secondary_currency": False}, False),
        ]
        for context, expected_mode in cases:
            with self.subTest(context=context):
                partner = self.partner.with_context(**context)
                self.assertEqual(partner._get_debt_report_currency_mode(), expected_mode)

    def test_both_currencies_include_all_lines(self):
        names = self._report_move_names(company_currency=True, secondary_currency=True)
        self.assertIn(self.local_move.name, names)
        self.assertIn(self.foreign_move.name, names)

    def test_only_secondary_currency_excludes_company_lines(self):
        names = self._report_move_names(company_currency=False, secondary_currency=True)
        self.assertEqual(names, [self.foreign_move.name])

    def test_only_company_currency_excludes_foreign_lines(self):
        names = self._report_move_names(company_currency=True, secondary_currency=False)
        self.assertEqual(names, [self.local_move.name])

    def test_currency_domain_pairs_each_company_with_its_own_currency(self):
        """Every company is judged against its own currency, not against a shared list."""
        company_only = self.partner._get_debt_report_currency_domain("company", self.company)
        self.assertIn(("company_currency_id", "=", self.company_currency.id), company_only)
        self.assertIn(("currency_id", "=", self.company_currency.id), company_only)
        self.assertIn(("company_id", "in", self.company.ids), company_only)
        secondary = self.partner._get_debt_report_currency_domain("secondary", self.company)
        self.assertIn(("amount_currency", "!=", 0.0), secondary)
        self.assertIn(("company_currency_id", "!=", self.company_currency.id), secondary)

    def test_no_currency_mode_means_no_clause(self):
        self.assertEqual(self.partner._get_debt_report_currency_domain(False, self.company), [])

    def test_no_company_is_exempt_by_default(self):
        """Nothing is exempt unless a company explicitly reconciles on its own currency."""
        self.assertFalse(self.partner._get_debt_report_unfiltered_companies(self.company))

    def test_foreign_line_without_amount_currency_only_shows_consolidated(self):
        """This is the shape of an exchange rate difference on a foreign item.

        It is born with the foreign currency but no amount in it, so it falls out of
        both individual views and only shows up in the consolidated one.
        """
        exchange_like_move = self._create_debt_move(25.0, amount_currency=0.0, currency=self.foreign_currency)
        receivable_line = self._receivable_line(exchange_like_move)
        self.assertEqual(receivable_line.currency_id, self.foreign_currency)
        self.assertEqual(receivable_line.amount_currency, 0.0)

        self.assertNotIn(
            exchange_like_move.name, self._report_move_names(company_currency=True, secondary_currency=False)
        )
        self.assertNotIn(
            exchange_like_move.name, self._report_move_names(company_currency=False, secondary_currency=True)
        )
        self.assertIn(exchange_like_move.name, self._report_move_names(company_currency=True, secondary_currency=True))

    def test_incomplete_currency_context_includes_all_lines(self):
        """Rendering without both keys -the distributor portal- stays consolidated."""
        for flags in [{}, {"secondary_currency": False}, {"company_currency": False}]:
            with self.subTest(**flags):
                names = self._report_move_names(**flags)
                self.assertIn(self.local_move.name, names)
                self.assertIn(self.foreign_move.name, names)


@tagged("post_install", "-at_install")
class TestDebtReportUnfilteredCompanies(DebtReportCommon):
    """Companies reconciling on their own currency keep every item in the report.

    Those book the exchange difference of a foreign document as a separate debit note in
    the company currency, so filtering would leave the note in without the document it
    adjusts and the balance would come out wrong.

    Runs post_install because the setting belongs to account_ux, which this module does
    not depend on and therefore loads after it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local_move = cls._create_debt_move(100.0)
        cls.foreign_move = cls._create_debt_move(50.0, amount_currency=100.0, currency=cls.foreign_currency)

    def _reconcile_on_company_currency(self):
        """Enable the setting, which account_ux only allows on Argentinian companies.

        Those in turn require global rounding, so both go in the same write to avoid an
        invalid intermediate state.
        """
        if "reconcile_on_company_currency" not in self.env["res.company"]._fields:
            self.skipTest("reconcile_on_company_currency needs account_ux installed")
        self.company.write(
            {
                "country_id": self.env.ref("base.ar").id,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        self.company.reconcile_on_company_currency = True

    def test_reconciling_on_company_currency_skips_the_filter(self):
        self._reconcile_on_company_currency()

        self.assertEqual(self.partner._get_debt_report_unfiltered_companies(self.company), self.company)
        self.assertEqual(self.partner._get_debt_report_currency_domain("company", self.company), [])
        # end to end: every item comes through whichever check is ticked
        for flags in [
            {"company_currency": True, "secondary_currency": False},
            {"company_currency": False, "secondary_currency": True},
        ]:
            with self.subTest(**flags):
                names = self._report_move_names(**flags)
                self.assertIn(self.local_move.name, names)
                self.assertIn(self.foreign_move.name, names)

    def test_the_filter_still_applies_without_the_setting(self):
        if "reconcile_on_company_currency" not in self.env["res.company"]._fields:
            self.skipTest("reconcile_on_company_currency needs account_ux installed")
        self.company.reconcile_on_company_currency = False
        names = self._report_move_names(company_currency=True, secondary_currency=False)
        self.assertEqual(names, [self.local_move.name])


class TestDebtReportInitialBalance(DebtReportCommon):
    """With a from_date the initial balance uses the same currency filter as the detail."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # before the report window: 100 in company currency and 100 foreign (50 converted)
        cls._create_debt_move(100.0, date="2024-01-10")
        cls._create_debt_move(50.0, amount_currency=100.0, currency=cls.foreign_currency, date="2024-01-10")
        # inside the report window, so the initial balance is not the only line
        cls._create_debt_move(30.0, date="2024-06-15")
        cls._create_debt_move(20.0, amount_currency=40.0, currency=cls.foreign_currency, date="2024-06-15")

    def _initial_balance_line(self, **currency_flags):
        return self._report_lines(from_date="2024-06-01", **currency_flags)[0]

    def test_initial_balance_both_currencies(self):
        line = self._initial_balance_line(company_currency=True, secondary_currency=True)
        self.assertEqual(line["balance_raw"], 150.0)
        self.assertEqual(line["amount_currency_raw"], 100.0)

    def test_initial_balance_only_company_currency(self):
        line = self._initial_balance_line(company_currency=True, secondary_currency=False)
        self.assertEqual(line["balance_raw"], 100.0)
        self.assertEqual(line["amount_currency_raw"], 0.0)

    def test_initial_balance_only_secondary_currency(self):
        line = self._initial_balance_line(company_currency=False, secondary_currency=True)
        self.assertEqual(line["balance_raw"], 50.0)
        self.assertEqual(line["amount_currency_raw"], 100.0)

    def test_balance_in_currency_continues_from_the_initial_one(self):
        """The currency balance column has to carry over what happened before from_date."""
        lines = self._report_lines(from_date="2024-06-01", company_currency=True, secondary_currency=True)
        self.assertEqual(lines[0]["balance_currency_raw"], 100.0)
        foreign_rows = [line for line in lines if line["amount_currency_raw"] == 40.0]
        self.assertEqual(len(foreign_rows), 1)
        self.assertEqual(foreign_rows[0]["balance_currency_raw"], 140.0)

    def test_initial_balance_in_currency_carries_its_label(self):
        line = self._initial_balance_line(company_currency=True, secondary_currency=True)
        self.assertTrue(line["amount_currency"].startswith(self.foreign_currency.display_name))

    def test_initial_balance_mixing_currencies_carries_no_label(self):
        """A sum of several foreign currencies cannot be attributed to any single one."""
        third_currency = self.env.ref("base.GBP")
        third_currency.active = True
        self._create_debt_move(10.0, amount_currency=20.0, currency=third_currency, date="2024-01-10")
        line = self._initial_balance_line(company_currency=True, secondary_currency=True)
        self.assertEqual(line["amount_currency_raw"], 120.0)
        self.assertFalse(line["amount_currency"].startswith(self.foreign_currency.display_name))


class TestDebtReportExchangeDifference(DebtReportCommon):
    """Where an exchange rate difference shows up follows from the currency it is in.

    The core books the difference on whichever reconciled line is settled in the
    reconciliation currency but still carries a residual in company currency, and the
    difference inherits that line's currency. Which line that is depends on both which
    side is foreign and the direction the rate moved, so a difference can end up in the
    foreign currency -out of both individual views- or in the company currency -shown in
    that view-. Both outcomes are pinned below. Either way they only surface with the
    full history, since exchange differences are born reconciled.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the foreign currency loses value between these two dates
        cls._set_foreign_rate("2024-06-01", 4.0)
        # ... and gains it between these other two, which flips which side of a
        # reconciliation is left with a residual in company currency
        cls._set_foreign_rate("2025-01-01", 4.0)
        cls._set_foreign_rate("2025-06-01", 2.0)

    def _exchange_difference_lines(self, first, second):
        """Reconcile both moves and return their exchange difference receivable lines."""
        lines = self._receivable_line(first) + self._receivable_line(second)
        lines.reconcile()
        return lines.exchange_move_ids.line_ids.filtered(lambda line: line.account_id == self.receivable_account)

    def _settle_foreign_item_in_company_currency(self):
        """Cross currency collection while the foreign currency loses value.

        In this direction the core is left correcting the foreign side.
        """
        foreign_move = self._create_debt_move(
            50.0, amount_currency=100.0, currency=self.foreign_currency, date="2024-01-10"
        )
        payment_move = self._create_debt_move(-60.0, date="2024-06-15")
        return self._exchange_difference_lines(foreign_move, payment_move)

    def test_difference_booked_in_the_foreign_currency_only_shows_consolidated(self):
        """Booked on a foreign line, it carries no amount in that currency either.

        So it falls out of both individual views and reconciles only on the consolidated
        one.
        """
        exchange_lines = self._settle_foreign_item_in_company_currency()

        self.assertTrue(exchange_lines)
        self.assertEqual(exchange_lines.currency_id, self.foreign_currency)
        self.assertEqual(exchange_lines.amount_currency, 0.0)

        exchange_move_names = exchange_lines.move_id.mapped("name")
        company_only = self._report_move_names(company_currency=True, secondary_currency=False)
        secondary_only = self._report_move_names(company_currency=False, secondary_currency=True)
        consolidated = self._report_move_names(company_currency=True, secondary_currency=True)
        for name in exchange_move_names:
            self.assertNotIn(name, company_only)
            self.assertNotIn(name, secondary_only)
            self.assertIn(name, consolidated)

    def test_difference_booked_in_the_company_currency_shows_in_company_mode(self):
        """Booked on a company currency line, filtering by currency cannot avoid it.

        It shows in the company currency statement next to the item it corrects, while
        the foreign counterpart of the reconciliation is not there.
        """
        local_move = self._create_debt_move(50.0, date="2024-01-10")
        foreign_move = self._create_debt_move(
            -25.0, amount_currency=-100.0, currency=self.foreign_currency, date="2024-06-15"
        )
        exchange_lines = self._exchange_difference_lines(local_move, foreign_move)

        self.assertTrue(exchange_lines)
        self.assertEqual(exchange_lines.currency_id, self.company_currency)

        exchange_move_names = exchange_lines.move_id.mapped("name")
        company_only = self._report_move_names(company_currency=True, secondary_currency=False)
        secondary_only = self._report_move_names(company_currency=False, secondary_currency=True)
        for name in exchange_move_names:
            self.assertIn(name, company_only)
            self.assertNotIn(name, secondary_only)

    def test_cross_currency_collection_with_a_gaining_currency_shows_in_company_mode(self):
        """The dominant case in Argentina, and the one the requirement was about.

        A document issued in the foreign currency, collected in company currency, with
        the foreign currency gaining value in between: the core is left correcting the
        company currency side, so the difference lands in that statement even though the
        document that generated it does not. Filtering by currency does not remove it.
        """
        foreign_move = self._create_debt_move(
            25.0, amount_currency=100.0, currency=self.foreign_currency, date="2025-01-10"
        )
        payment_move = self._create_debt_move(-40.0, date="2025-06-15")
        exchange_lines = self._exchange_difference_lines(foreign_move, payment_move)

        self.assertTrue(exchange_lines)
        self.assertEqual(exchange_lines.currency_id, self.company_currency)
        self.assertIn(
            exchange_lines.move_id.name,
            self._report_move_names(company_currency=True, secondary_currency=False),
        )
        self.assertNotIn(
            foreign_move.name,
            self._report_move_names(company_currency=True, secondary_currency=False),
        )

    def test_exchange_differences_are_hidden_outside_the_full_history(self):
        """Exchange differences are born reconciled, so pending balances never show them."""
        exchange_lines = self._settle_foreign_item_in_company_currency()
        self.assertTrue(exchange_lines)

        for flags in [
            {"company_currency": True, "secondary_currency": False},
            {"company_currency": False, "secondary_currency": True},
            {"company_currency": True, "secondary_currency": True},
        ]:
            with self.subTest(**flags):
                names = self._report_move_names(historical_full=False, **flags)
                for name in exchange_lines.move_id.mapped("name"):
                    self.assertNotIn(name, names)


class TestAccountDebtReportWizard(TransactionCase):
    def setUp(self):
        super(TestAccountDebtReportWizard, self).setUp()
        # Crear un partner de prueba
        self.partner = self.env["res.partner"].create({"name": "Test Partner", "email": "test@example.com"})
        self.partner_2 = self.env["res.partner"].create({"name": "Test Partner 2", "email": "test2@example.com"})
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

    def test_default_currencies_are_both(self):
        """Printing without touching the wizard shows the whole debt, not only one currency."""
        wizard = self.env["account.debt.report.wizard"].create({})
        self.assertTrue(wizard.company_currency)
        self.assertTrue(wizard.secondary_currency)

    def test_confirm_passes_currency_flags_in_context(self):
        """The report reads the flags from the context, so they have to travel there."""
        action = self.wizard.with_context(
            active_ids=[self.partner.id],
            # otherwise report_action returns the report layout wizard instead
            discard_logo_check=True,
        ).confirm()
        self.assertTrue(action["context"]["company_currency"])
        self.assertTrue(action["context"]["secondary_currency"])

    def test_at_least_one_currency_is_required(self):
        with self.assertRaises(ValidationError):
            self.wizard.write({"company_currency": False, "secondary_currency": False})

    def test_send_by_email_method_single_partner_uses_comment(self):
        action = self.wizard.with_context(active_id=self.partner.id).send_by_email()
        self.assertTrue(action, "El método send_by_email debería retornar una acción de ventana")
        self.assertEqual(action["res_model"], "mail.compose.message", "El modelo debería ser 'mail.compose.message'")
        self.assertEqual(action["context"]["default_composition_mode"], "comment")
        self.assertEqual(action["context"]["active_ids"], [])
        self.assertEqual(action["context"]["active_id"], self.partner.id)
        self.assertEqual(action["context"]["default_res_ids"], [self.partner.id])
        self.assertEqual(action["context"]["default_partner_to"], "{{ object.id or '' }}")

    def test_send_by_email_method_multiple_partners_uses_mass_mail(self):
        action = self.wizard.with_context(active_ids=[self.partner.id, self.partner_2.id]).send_by_email()
        self.assertTrue(action, "El método send_by_email debería retornar una acción de ventana")
        self.assertEqual(action["context"]["default_composition_mode"], "mass_mail")
        self.assertEqual(action["context"]["active_ids"], [self.partner.id, self.partner_2.id])
        self.assertEqual(action["context"]["default_res_ids"], [self.partner.id, self.partner_2.id])
        self.assertEqual(action["context"]["default_partner_to"], "{{ object.id or '' }}")
