##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools.misc import format_date, formatLang


class AccountDebtReport(models.AbstractModel):
    """Lines of the debt report of a partner.

    Every option comes from the context, which is the only channel shared by the
    download and the email. The spreadsheet gets the amounts as numbers, each cell
    formatted with its own currency, since one sheet can mix currencies; the PDF
    gets them as text with their symbol.
    """

    _name = "account.debt.report"
    _description = "Account Debt Report"

    @api.model
    def _get_currency_mode(self):
        """Currency mode requested for the report: "company", "secondary" or False.

        The wizard lets the user tick the company currency, the secondary one or both.
        Asking for both -or for none, which is what happens when the report is rendered
        without these context keys- means the consolidated report, so we don't filter.
        """
        company_currency = bool(self.env.context.get("company_currency"))
        secondary_currency = bool(self.env.context.get("secondary_currency"))
        if company_currency == secondary_currency:
            return False
        return "company" if company_currency else "secondary"

    @api.model
    def _get_unfiltered_companies(self, companies):
        """Companies whose items are never narrowed down by currency.

        A company reconciling on its own currency books the exchange difference of a
        foreign document as a separate debit note in the company currency. Filtering
        would leave that note in without the document it adjusts, and the balance would
        come out wrong, so those companies keep the behaviour they had before the filter
        existed. The setting belongs to account_ux, which this module does not depend on,
        hence checking that the field is there at all.
        """
        if "reconcile_on_company_currency" not in companies._fields:
            return companies.browse()
        return companies.filtered("reconcile_on_company_currency")

    @api.model
    def _get_currency_domain(self, currency_mode, companies):
        """Domain restricting the items to the currency requested for the report.

        An item is issued in the company currency when the currency it carries is the
        currency of its own company, both of them stored on the line. Pairing them keeps
        the filter exact even when the report spans companies with different currencies.
        """
        if not currency_mode:
            return []
        in_company_currency = Domain.OR(
            [
                Domain("company_currency_id", "=", currency.id) & Domain("currency_id", "=", currency.id)
                for currency in companies.mapped("currency_id")
            ]
        )
        if currency_mode == "secondary":
            # a company-currency item never belongs in a foreign-currency-only report,
            # not even for the companies exempt below: mixing it in would add
            # company-currency amounts into a total meant to be in a single foreign
            # currency.
            return list(~in_company_currency & Domain("amount_currency", "!=", 0.0))
        unfiltered = self._get_unfiltered_companies(companies)
        filtered = companies - unfiltered
        if not filtered:
            return []
        # the filter only governs the companies it applies to
        domain = in_company_currency & Domain("company_id", "in", filtered.ids)
        if unfiltered:
            domain |= Domain("company_id", "in", unfiltered.ids)
        return list(domain)

    @api.model
    def _get_detail_lines(self, move):
        """Text lines that detail a move in the report.

        Only the product lines of an invoice have a quantity, and a unit when they carry one.
        The rest (sections, notes, payments, exchange differences) show their description.
        """
        is_invoice = move.is_invoice(include_receipts=True)
        detail_lines = []
        for line in move.invoice_line_ids:
            text = (line.name or "Sin descripción").replace("\n", " ").replace("\r", "")
            if is_invoice and line.display_type == "product":
                text = "%s x %s" % (text, line.quantity)
                if line.product_uom_id:
                    text = "%s %s" % (text, line.product_uom_id.name)
            text = "* " + text
            # an entry repeats the same description on both sides of its lines
            if not is_invoice and text in detail_lines:
                continue
            detail_lines.append(text)
        return detail_lines

    @api.model
    def _get_companies(self):
        company_id = self.env.context.get("company_id")
        return self.env["res.company"].browse(company_id) if company_id else self.env.companies

    @api.model
    def _get_domain(self, partner, companies, currency_mode):
        ctx = self.env.context
        domain = [
            ("partner_id", "=", partner.id),
            ("parent_state", "=", "posted"),
            ("company_id", "in", companies.ids),
        ]
        domain += self._get_currency_domain(currency_mode, companies)
        # without the full history only what is still pending shows up
        if not ctx.get("historical_full"):
            domain += [("reconciled", "=", False), ("full_reconcile_id", "=", False)]
        result_selection = ctx.get("result_selection")
        if result_selection == "receivable":
            domain += [("account_type", "=", "asset_receivable")]
        elif result_selection == "payable":
            domain += [("account_type", "=", "liability_payable")]
        else:
            domain += [("account_type", "in", ["asset_receivable", "liability_payable"])]
        return domain

    @api.model
    def _get_initial_line(self, partner, initial_domain, companies, currency_mode):
        groups = (
            self.env["account.move.line"]
            .sudo()
            ._read_group(initial_domain, groupby=["partner_id"], aggregates=["balance:sum"])
        )
        balance = groups[0][1] if groups else 0.0
        balance_currency, currency_name = 0.0, ""
        # asking only for the company currency leaves no secondary amount to show,
        # and the domain of _get_currency_balance would contradict the one above
        if currency_mode != "company":
            balance_currency, currency_name = self._get_currency_balance(initial_domain, companies)
        company_currencies = companies.mapped("currency_id")
        return {
            "date": False,
            "date_maturity": False,
            "name": _("INITIAL BALANCE"),
            "detail_lines": [],
            # the row stands for no document, so what the period starts from is
            # stated as a balance and the amount columns are left empty
            "amount": False,
            "amount_residual": False,
            "balance": balance,
            "amount_currency": False,
            "amount_residual_currency": False,
            "balance_currency": balance_currency,
            "company_currency": company_currencies if len(company_currencies) == 1 else False,
            "currency": False,
            "currency_name": currency_name,
        }

    @api.model
    def _format_amount(self, amount, currency=False, label=False):
        if amount is False or amount is None:
            return False
        digits = currency.decimal_places if currency else 2
        number = formatLang(self.env, abs(amount), digits=digits).replace("\N{NO-BREAK SPACE}", " ")
        label = label or (currency and (currency.symbol or currency.name))
        text = f"{label} {number}" if label else number
        return f"- {text}" if amount < 0 else text

    @api.model
    def _get_lines(self, partner):
        """Rows of the report for a partner, with the amounts as text for the template."""
        lines = self._compute_lines(partner)
        for line in lines:
            company_currency = line["company_currency"]
            for key in ("amount", "amount_residual", "balance"):
                line[key] = self._format_amount(line[key], company_currency)
            for key in ("amount_currency", "amount_residual_currency", "balance_currency"):
                line[key] = self._format_amount(line[key], line["currency"], line["currency_name"])
        return lines

    @api.model
    def _get_columns(self):
        """Amount columns of the report as (key, title), following the wizard options."""
        ctx = self.env.context
        company_currency = ctx.get("company_currency")
        secondary_currency = ctx.get("secondary_currency")
        # without any of the two, as when rendered with no context, both are shown
        if not company_currency and not secondary_currency:
            company_currency = secondary_currency = True
        historical_full = ctx.get("historical_full")
        columns = []
        if company_currency:
            columns.append(("amount", _("Amount")))
            if not historical_full:
                columns.append(("amount_residual", _("Residual")))
            columns.append(("balance", _("Balance")))
        if secondary_currency:
            columns.append(("amount_currency", _("Amount in Currency")))
            if not historical_full:
                columns.append(("amount_residual_currency", _("Residual in Currency")))
            columns.append(("balance_currency", _("Balance in Currency")))
        return columns

    @api.model
    def _get_title(self, partner):
        ctx = self.env.context
        kind = _("History") if ctx.get("historical_full") else _("Current Account")
        to_date = fields.Date.to_date(ctx.get("to_date")) or fields.Date.context_today(self)
        return (
            _("Account Summary (%s)", kind),
            _("%(partner)s as of %(date)s", partner=partner.name, date=self._format_date(to_date)),
        )

    @api.model
    def _format_date(self, date):
        return format_date(self.env, date)

    @api.model
    def _get_xlsx_date_format(self):
        """Spreadsheet date format matching the date format of the user language."""
        lang = self.env["res.lang"]._get_data(code=self.env.lang or "en_US")
        date_format = lang.date_format or "%m/%d/%Y"
        for posix, excel in (("%d", "dd"), ("%m", "mm"), ("%Y", "yyyy"), ("%y", "yy"), ("%b", "mmm"), ("%B", "mmmm")):
            date_format = date_format.replace(posix, excel)
        return date_format

    @api.model
    def _get_xlsx_amount_format(self, currency=False, label=False):
        """Number format with the currency inside the cell, so the number stays a number.

        Negatives read "- $ 1.234,56" and the label always goes first, as in the PDF.
        """
        digits = currency.decimal_places if currency else 2
        number = "#,##0" + ("." + "0" * digits if digits else "")
        label = (label or (currency and (currency.symbol or currency.name)) or "").replace('"', "")
        prefix = f"{label} " if label else ""
        positive = f'"{prefix}"{number}' if prefix else number
        return f'{positive};"- {prefix}"{number}'

    @api.model
    def _write_xlsx(self, workbook, partners):
        """Debt of the commercial partner of each partner, one after the other."""
        sheet = workbook.add_worksheet(_("Debt Report"))
        bold = workbook.add_format({"bold": True})
        header = workbook.add_format({"bold": True, "bottom": 1})
        date_format = workbook.add_format({"num_format": self._get_xlsx_date_format()})
        amount_formats = {}

        def amount_format(currency, label):
            key = (currency.id if currency else False, label or "")
            if key not in amount_formats:
                amount_formats[key] = workbook.add_format({"num_format": self._get_xlsx_amount_format(currency, label)})
            return amount_formats[key]

        columns = self._get_columns()
        headers = [_("Date"), _("Due Date"), _("Description")] + [title for _key, title in columns]
        sheet.set_column(0, 1, 12)
        sheet.set_column(2, 2, 50)
        sheet.set_column(3, 2 + len(columns), 18)
        row = 0
        for partner in partners.commercial_partner_id:
            title, subtitle = self._get_title(partner)
            sheet.write(row, 0, title, bold)
            sheet.write(row + 1, 0, subtitle, bold)
            row += 3
            sheet.write_row(row, 0, headers, header)
            row += 1
            for line in self._compute_lines(partner):
                for col, key in enumerate(("date", "date_maturity")):
                    if line[key]:
                        sheet.write_datetime(row, col, fields.Datetime.to_datetime(line[key]), date_format)
                sheet.write(row, 2, line["name"])
                for col, (key, _title) in enumerate(columns, start=3):
                    if line[key] is False:
                        continue
                    if key.endswith("_currency"):
                        cell_format = amount_format(line["currency"], line["currency_name"])
                    else:
                        cell_format = amount_format(line["company_currency"], False)
                    sheet.write_number(row, col, line[key], cell_format)
                row += 1
                for detail_line in line["detail_lines"]:
                    sheet.write(row, 2, detail_line)
                    row += 1
            row += 1

    @api.model
    def _compute_lines(self, partner):
        """Rows of the report for a partner, the initial balance first when there is a from_date."""
        partner.ensure_one()
        ctx = self.env.context
        from_date = ctx.get("from_date")
        to_date = ctx.get("to_date")
        historical_full = ctx.get("historical_full")
        show_invoice_detail = ctx.get("show_invoice_detail")
        currency_mode = self._get_currency_mode()
        companies = self._get_companies()
        domain = self._get_domain(partner, companies, currency_mode)

        res = []
        balance = balance_currency = 0.0
        if from_date:
            initial_line = self._get_initial_line(
                partner, domain + [("date", "<", from_date)], companies, currency_mode
            )
            res.append(initial_line)
            balance = initial_line["balance"]
            # the running balance in currency starts off the initial one too, otherwise
            # its column ignores everything before from_date
            balance_currency = initial_line["balance_currency"]
            domain.append(("date", ">=", from_date))
        if to_date:
            domain.append(("date", "<=", to_date))

        balance_field = "balance" if historical_full else "amount_residual"
        currency_field = "amount_currency" if historical_full else "amount_residual_currency"
        records = (
            self.env["account.move.line"]
            .sudo()
            .search(domain, order="date asc, name, move_id desc, date_maturity asc, id")
        )
        for record in records:
            name = record.move_id.name
            if record.ref and record.ref != "/":
                name += " - " + record.ref
            if record.payment_id:
                name += " - " + record.journal_id.name
            company_currency = record.company_id.currency_id
            show_currency = record.currency_id != company_currency
            # rounded so float noise from the running sum never reaches the formatted text
            balance = company_currency.round(balance + record[balance_field])
            if show_currency:
                balance_currency = record.currency_id.round(balance_currency + record[currency_field])
            res.append(
                {
                    "date": record.date,
                    "date_maturity": record.date_maturity,
                    "name": name,
                    "detail_lines": self._get_detail_lines(record.move_id) if show_invoice_detail else [],
                    "amount": record.balance,
                    "amount_residual": record.amount_residual,
                    "balance": balance,
                    "amount_currency": record.amount_currency if show_currency else False,
                    "amount_residual_currency": record.amount_residual_currency if show_currency else False,
                    "balance_currency": balance_currency if show_currency else False,
                    "company_currency": company_currency,
                    "currency": record.currency_id if show_currency else False,
                    "currency_name": record.currency_id.display_name if show_currency else "",
                }
            )
        return res

    @api.model
    def _get_currency_balance(self, initial_domain, companies):
        groups = (
            self.env["account.move.line"]
            .sudo()
            ._read_group(
                # same notion of "issued in a foreign currency" as the detail uses
                initial_domain + self._get_currency_domain("secondary", companies),
                groupby=["partner_id"],
                aggregates=["amount_currency:sum", "currency_id:array_agg"],
            )
        )
        if not groups:
            return 0.0, ""
        _partner, balance_currency, currency_ids = groups[0]
        # only label the amount when every item shares one currency: the sum of
        # several foreign currencies cannot be attributed to any single one
        currencies = self.env["res.currency"].browse(set(currency_ids or []))
        return balance_currency, currencies.display_name if len(currencies) == 1 else ""
