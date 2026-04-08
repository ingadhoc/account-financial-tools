import html
import logging
import traceback

from odoo import Command, _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    config_warning = fields.Html(
        compute="_compute_config_warning",
    )
    bank_statements_source = fields.Selection(default="no_statement")

    def __get_bank_statements_available_sources(self):
        """Add 'No statement' option to bank feeds"""
        rslt = super().__get_bank_statements_available_sources()
        rslt = [("no_statement", _("No statement"))] + rslt
        return rslt

    @api.depends(
        "default_account_id",
        "bank_statements_source",
        "inbound_payment_method_line_ids.code",
        "inbound_payment_method_line_ids.payment_account_id",
        "outbound_payment_method_line_ids.code",
        "outbound_payment_method_line_ids.payment_account_id",
    )
    def _compute_config_warning(self):
        bank_cash_journals = self.filtered(lambda j: j.type in ["bank", "cash", "credit"])
        (self - bank_cash_journals).config_warning = ""

        for journal in bank_cash_journals:
            warnings = []

            if not journal._origin:
                journal.config_warning = ""
                continue

            all_lines = journal.inbound_payment_method_line_ids + journal.outbound_payment_method_line_ids
            if not all_lines:
                journal.config_warning = ""
                continue

            check_codes = ["own_checks", "check_printing"]
            non_check_lines = all_lines.filtered(lambda l: l.code not in check_codes)
            lines_without_account = all_lines.filtered(lambda l: not l.payment_account_id)
            uses_reconciliation = journal.bank_statements_source != "no_statement"

            # 1. Validar métodos de pago sin cuenta
            if len(lines_without_account) == len(all_lines):
                warnings.append(
                    (
                        "danger",
                        "Este diario no generará asientos contables porque ningún método de pago tiene cuenta configurada.",
                    )
                )
            elif lines_without_account:
                method_names = ", ".join(lines_without_account.mapped("name"))
                warnings.append(
                    (
                        "warning",
                        f"Los siguientes métodos no generarán asientos: {method_names}. "
                        "Verifique que esta configuración sea intencional.",
                    )
                )

            # 2. Validar coherencia entre conciliación y cuentas (solo para líneas no-cheques)
            if non_check_lines:
                lines_with_account = non_check_lines.filtered(lambda l: l.payment_account_id)
                all_pending = all(l.payment_account_id.account_type == "asset_current" for l in lines_with_account)
                all_direct = all(l.payment_account_id == journal.default_account_id for l in lines_with_account)
                some_direct = any(l.payment_account_id == journal.default_account_id for l in lines_with_account)

                if all_pending and not uses_reconciliation:
                    warnings.append(
                        (
                            "warning",
                            "La conciliación está desactivada, pero las cuentas requieren conciliación. "
                            "Los pagos quedarán pendientes sin forma de conciliarlos.",
                        )
                    )
                elif all_direct and uses_reconciliation:
                    warnings.append(
                        (
                            "warning",
                            "La conciliación está activada, pero los pagos irán directo a la cuenta "
                            "del diario. No habrá nada que conciliar.",
                        )
                    )
                elif some_direct and not all_direct:
                    warnings.append(
                        (
                            "danger",
                            "Configuración de cuentas inconsistente: algunos métodos usan cuentas pendientes "
                            "y otros van directo a liquidez. Revise 'Pagos entrantes' y 'Pagos salientes'. "
                            '<a target="_blank" href="https://www.odoo.com/documentation/19.0/es/applications/finance/accounting/payments.html">'
                            "Más información.</a>",
                        )
                    )

            # 3. Validar cuenta de cheques diferidos
            bad_check_lines = journal.outbound_payment_method_line_ids.filtered(
                lambda l: (
                    l.code in check_codes
                    and l.payment_account_id
                    and l.payment_account_id.account_type != "liability_current"
                )
            )
            if bad_check_lines:
                warnings.append(
                    (
                        "warning",
                        "Los cheques diferidos deberían usar una cuenta de tipo 'Pasivo Circulante' "
                        "para reflejar correctamente la obligación de pago.",
                    )
                )

            # Formatear resultado
            if warnings:
                journal.config_warning = html.unescape(
                    "".join(
                        f'<div class="alert alert-{alert}" role="alert" style="margin-bottom:0px;">{msg}</div>'
                        for alert, msg in warnings
                    )
                )
            else:
                journal.config_warning = ""

    @api.model_create_multi
    def create(self, vals_list):
        # DEBUG: detect journal creates without name that will cause account_account.name = NULL
        for vals in vals_list:
            if (
                vals.get("type") in ["bank", "cash", "credit"]
                and not vals.get("name")
                and not vals.get("bank_acc_number")
                and not vals.get("name_placeholder")
            ):
                _logger.warning(
                    "JOURNAL CREATE WITHOUT NAME detected (type=%s, company_id=%s). "
                    "This will trigger account_account NOT NULL failure.\nCall stack:\n%s",
                    vals.get("type"),
                    vals.get("company_id"),
                    "".join(traceback.format_stack()),
                )
        journals = super().create(vals_list)
        for journal in journals.filtered(lambda x: x.type in ["bank", "cash", "credit"]):
            company = self.env["res.company"].browse(journal.company_id.id) if journal.company_id else self.env.company
            use_no_statement = journal.type in ["bank", "credit"] and journal.bank_statements_source == "no_statement"
            # Use default_account_id for cash journals or bank/credit journals with 'no_statement'
            if journal.type == "cash" or use_no_statement:
                payment_account_id = journal.default_account_id.id
                if use_no_statement and "check_add_debit_button" in journal._fields:
                    journal.check_add_debit_button = True
                    # We create the outstanding account anyway but deactivate it if no statement is used
                    outstanding_accounts_ids = self._create_outstanding_account(company, journal)
                    self.env["account.account"].browse(outstanding_accounts_ids).write({"active": False})
            else:
                payment_account_id = self._create_outstanding_account(company, journal)

            # Create deferred account for checks
            check_methods = journal.outbound_payment_method_line_ids.filtered(
                lambda l: l.code in ["own_checks", "check_printing"]
            )
            deferred_account_id = None
            if check_methods:
                deferred_account_id = self._create_deferred_account(company, journal)

            journal._update_payment_method_line_accounts(payment_account_id, deferred_account_id)

        return journals

    def write(self, vals):
        if "bank_statements_source" in vals:
            for journal in self.filtered(lambda x: x.type in ["bank", "credit"] and not x.has_entries):
                if vals["bank_statements_source"] == "no_statement":
                    journal._update_payment_method_line_accounts(self.default_account_id.id)
                elif (
                    journal.bank_statements_source == "no_statement"
                    and vals["bank_statements_source"] != "no_statement"
                ):
                    # Find the outstanding account created for this journal
                    # Search by name pattern that was set in _prepare_outstanding_account_vals
                    account_name = _("Outstanding %s") % journal.name
                    account = (
                        self.env["account.account"]
                        .with_context(active_test=False)
                        .search(
                            [
                                ("name", "=", account_name),
                                ("company_ids", "in", journal.company_id.id),
                                ("account_type", "=", "asset_current"),
                            ],
                            limit=1,
                        )
                    )
                    if account:
                        if not account.active:
                            account.write({"active": True})
                        # Update payment method lines to use this account
                        journal._update_payment_method_line_accounts(account.id)

        return super().write(vals)

    @api.model
    def _create_outstanding_account(self, company, journal):
        random_account = (
            self.env["account.account"]
            .with_company(company)
            .with_context(active_test=False)
            .search(
                self.env["account.account"]._check_company_domain(company),
                limit=1,
            )
        )
        digits = len(random_account.code) if random_account else 6

        account_prefix = company.bank_account_code_prefix or ""
        start_code = account_prefix.ljust(digits, "0")
        account_code = self.env["account.account"].with_company(company)._search_new_account_code(start_code)
        account_vals = self._prepare_outstanding_account_vals(company, account_code, journal)

        account = self.env["account.account"].create(account_vals)
        if account:
            self.env["ir.model.data"]._update_xmlids(
                [
                    {
                        "xml_id": f"account.{company.id}_bank_outstanding_journal_account_{account.id}",
                        "record": account,
                        "noupdate": True,
                    }
                ]
            )

        return account.id

    @api.model
    def _prepare_outstanding_account_vals(self, company, code, journal):
        return {
            "name": _("Outstanding %s") % journal.name,
            "code": code,
            "account_type": "asset_current",
            "currency_id": journal.currency_id.id,
            "company_ids": [Command.link(company.id)],
            "reconcile": True,
        }

    @api.model
    def _create_deferred_account(self, company, journal):
        random_account = (
            self.env["account.account"]
            .with_company(company)
            .with_context(active_test=False)
            .search(
                self.env["account.account"]._check_company_domain(company),
                limit=1,
            )
        )
        digits = len(random_account.code) if random_account else 6

        account_prefix = company.bank_account_code_prefix or ""
        start_code = account_prefix.ljust(digits, "0")
        account_code = self.env["account.account"].with_company(company)._search_new_account_code(start_code)
        account_vals = self._prepare_deferred_account_vals(company, account_code, journal)

        account = self.env["account.account"].create(account_vals)
        if account:
            self.env["ir.model.data"]._update_xmlids(
                [
                    {
                        "xml_id": f"account.{company.id}_bank_deferred_journal_account_{account.id}",
                        "record": account,
                        "noupdate": True,
                    }
                ]
            )

        return account.id

    @api.model
    def _prepare_deferred_account_vals(self, company, code, journal):
        return {
            "name": _("Deferred Checks %s") % journal.name,
            "code": code,
            "account_type": "liability_current",
            "currency_id": journal.currency_id.id,
            "company_ids": [Command.link(company.id)],
            "reconcile": True,
        }

    def _update_payment_method_line_accounts(self, payment_account_id, deferred_account_id=None):
        # Update all inbound payment methods
        self.inbound_payment_method_line_ids.write({"payment_account_id": payment_account_id})

        # Update outbound payment method lines (except checks)
        for line in self.outbound_payment_method_line_ids:
            if line.code in ["own_checks", "check_printing"]:
                if deferred_account_id:
                    line.write({"payment_account_id": deferred_account_id})
            else:
                line.write({"payment_account_id": payment_account_id})

    def fetch_online_sync_favorite_institutions(self):
        """Evitamos la llamada HTTP a OdooFin que tarda 2.5s+ y no necesitamos."""
        return []
