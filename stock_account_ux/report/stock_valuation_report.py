from ast import literal_eval
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

# Valid values of the Movement Type filter.
LINE_TYPE_STOCK_MOVE = "stock_move"
LINE_TYPE_PRODUCT_VALUE = "product_value"
VALID_LINE_TYPES = (LINE_TYPE_STOCK_MOVE, LINE_TYPE_PRODUCT_VALUE)


class StockValuationReport(models.AbstractModel):
    _inherit = "stock_account.stock.valuation.report"

    # -- Client action entry point --------------------------------------------
    @api.model
    def get_report_values(
        self,
        date=False,
        product_ids=None,
        categ_ids=None,
        cost_methods=None,
        valuations=None,
        line_types=None,
    ):
        """Extend the standard signature (``date`` only) with the report filters. All
        of them are optional: with none, the standard is used as is."""
        data = self.with_context(allowed_company_ids=self.env.company.ids)._get_report_data(
            date=date,
            product_ids=product_ids,
            categ_ids=categ_ids,
            cost_methods=cost_methods,
            valuations=valuations,
            line_types=line_types,
        )
        self._add_variation_drilldown_types(
            data,
            date,
            {
                "product_ids": product_ids,
                "categ_ids": categ_ids,
                "cost_methods": cost_methods,
                "valuations": valuations,
            },
        )
        return {"data": data, "context": {}}

    def _get_report_data(
        self,
        date=False,
        product_category=False,
        warehouse=False,
        product_ids=None,
        categ_ids=None,
        cost_methods=None,
        valuations=None,
        line_types=None,
    ):
        """Build the report data, honouring the filters.

        With no filter, the standard code runs untouched, so there is no regression.
        With filters, the filtered path applies two scoped changes: (A) it restricts
        ``valued_products``, and (B) it rebuilds the Stock Variation section per origin
        when the Movement Type filter is on.

        MAINTENANCE NOTE: the filtered path is a copy of
        ``stock_account/report/stock_valuation_report.py::_get_report_data`` (v19.0) and
        has to be re-synced on Odoo upgrades. ``test_no_filters_matches_filter_all``
        covers that drift.

        Being a copy, it does NOT go through the standard ``_get_report_data``: a module
        that extends the report by overriding that method would be silently skipped
        whenever a filter is active. Hook the HELPERS instead — ``_get_filtered_valued_products``,
        ``_get_report_accounting_data``, ``_get_variation_balances_by_account``,
        ``_get_variation_aml_vals`` — which both paths do share.
        """
        line_types = self._normalize_line_types(line_types)
        if not any([product_ids, categ_ids, cost_methods, valuations, line_types]):
            return super()._get_report_data(date=date, product_category=product_category, warehouse=warehouse)

        company = self.env.company
        date = self._normalize_report_date(date)

        # -- (A) Products scoped by the filters --------------------------------
        valued_products = self._get_filtered_valued_products(
            company, date, product_ids, categ_ids, cost_methods, valuations
        )

        # A filter matching ZERO products has to stop here. Passing an empty
        # recordset/dict to ``_get_accounts_by_product`` / ``stock_value`` /
        # ``stock_accounting_value`` backfires: they all test ``if not products`` /
        # ``if not accounts_by_product``, and empty is falsy, so they would fall back
        # to ALL products and the report would show the total instead of nothing.
        if not valued_products:
            return self._empty_valuation_report_data(company)

        # With a product filter on, the Initial Balance reads only the journal items
        # attributable to those products. The Movement Type filter does NOT count as
        # one: it scopes no product, and dropping the no-product balance there would
        # break the starting point of the breakdown per origin.
        product_scope = bool(product_ids or categ_ids or cost_methods or valuations)
        accounts_by_product = company._get_accounts_by_product(products=valued_products)
        inventory_data = company.stock_value(accounts_by_product, at_date=date or None)
        accounting_data = self._get_report_accounting_data(
            company, accounts_by_product, valued_products, date, product_scope
        )

        accounts = inventory_data.keys() | accounting_data.keys()
        account_ids = {acc.id for acc in accounts}

        initial_balance = {
            "label": _("Initial Balance"),
            "value": 0,
            "lines_by_account_id": defaultdict(lambda: {"value": 0}),
        }
        ending_stock = {
            "label": _("Ending Stock"),
            "value": 0,
            "lines_by_account_id": defaultdict(lambda: {"value": 0}),
        }

        for account in accounts:
            opening_balance = accounting_data.get(account, 0)
            ending_balance = inventory_data.get(account, 0)
            account_ids.add(account.id)
            if opening_balance:
                initial_balance["value"] += opening_balance
                initial_balance["lines_by_account_id"][account.id]["value"] += opening_balance
            if ending_balance:
                ending_stock["value"] += ending_balance
                ending_stock["lines_by_account_id"][account.id]["value"] += ending_balance

        location_valuation_vals = company._get_location_valuation_vals(
            date,
            location_domain=[("usage", "=", "inventory")],
        )

        report_data = {
            "company_id": company.id,
            "currency_id": company.currency_id.id,
            "ending_stock": ending_stock,
            "initial_balance": initial_balance,
        }

        if self._must_include_inventory_loss():
            inventory_loss = {"label": _("Inventory Loss"), "value": 0}
            lines_by_account_id = defaultdict(lambda: {"debit": 0, "credit": 0})
            for vals in location_valuation_vals:
                account_ids.add(vals["account_id"])
                inventory_loss["value"] -= vals["debit"]
                lines_by_account_id[vals["account_id"]]["debit"] += vals["debit"]
                lines_by_account_id[vals["account_id"]]["credit"] += vals["credit"]
            inventory_loss["lines"] = [
                {
                    "account_id": account_id,
                    "debit": vals["debit"],
                    "credit": vals["credit"],
                }
                for (account_id, vals) in lines_by_account_id.items()
            ]
            report_data["inventory_loss"] = inventory_loss

        # -- (B) Stock Variation section ---------------------------------------
        if line_types:
            # Movement Type filter: the variation is broken down per origin. Stock
            # Moves is the unaccounted physical moves; Product Value is the REMAINDER
            # (native total variation minus the stock part), which catches revaluations
            # with and without ``move_id``.
            filtered_balances = self._get_variation_balances_by_account(
                company, valued_products, accounts_by_product, date, line_types, inventory_data, accounting_data
            )
            stock_valuation_account_vals = self._get_variation_aml_vals(company, filtered_balances)
            # Ending Stock is projected as Initial Balance + filtered variation, so the
            # report adds up: filtered per origin it stops being the real state of the
            # stock and becomes the booked value it would have if ONLY that portion were
            # booked, which is exactly what the entry generated with this filter books.
            # Initial Balance is left alone: it is the already booked starting point, a
            # balance with no origin (historical entries do not record which origin they
            # come from), not a flow.
            ending_stock["value"] = 0
            ending_stock["lines_by_account_id"] = defaultdict(lambda: {"value": 0})
            for account in accounts | filtered_balances.keys():
                projected = accounting_data.get(account, 0) + filtered_balances.get(account, 0)
                if not projected:
                    continue
                account_ids.add(account.id)
                ending_stock["value"] += projected
                ending_stock["lines_by_account_id"][account.id]["value"] += projected
        elif product_scope:
            # With a product filter the variation is built from the attributable balance
            # computed above, not by delegating to the standard: that one recomputes the
            # balance on its own (through a method other modules reimplement), so it
            # would bring back the whole account balance and the report would not add up.
            stock_valuation_account_vals = self._get_variation_aml_vals(
                company, self._get_total_variation_balance(company, date, inventory_data, accounting_data)
            )
        else:
            stock_valuation_account_vals = company.with_context(
                inventory_data=inventory_data
            )._get_stock_valuation_account_vals(accounts_by_product, date, company._get_location_valuation_vals(date))

        stock_variation = {"label": _("Stock Variation"), "value": 0}
        lines_by_account_id = defaultdict(lambda: {"debit": 0, "credit": 0, "lines": []})
        for vals in stock_valuation_account_vals:
            account_ids.add(vals["account_id"])
            stock_variation["value"] += vals["debit"]
            lines_by_account_id[vals["account_id"]]["debit"] += vals["debit"]
            lines_by_account_id[vals["account_id"]]["credit"] += vals["credit"]
        stock_variation["lines"] = [
            {
                "account_id": account_id,
                "debit": vals["debit"],
                "credit": vals["credit"],
            }
            for (account_id, vals) in lines_by_account_id.items()
        ]

        accounts_read_data = self.env["account.account"].search_read(
            [("id", "in", list(account_ids))],
            ["id", "name", "code", "display_name"],
        )
        report_data.update(
            accounts_by_id={acc_data["id"]: acc_data for acc_data in accounts_read_data},
            stock_variation=stock_variation,
        )
        return report_data

    # -- Drill-down ------------------------------------------------------------
    @api.model
    def action_open_account_ledger(self, account_id, date=False):
        """Initial Balance to the General Ledger of that account, up to the report date.

        The General Ledger lives in ``account_reports`` (enterprise). The module does
        not declare it in ``depends``, so it is resolved at runtime and falls back to
        the journal items list when it is not installed.
        """
        account = self.env["account.account"].browse(int(account_id)).exists()
        if not account:
            raise UserError(self.env._("The account no longer exists."))
        general_ledger = self.env.ref("account_reports.action_account_report_general_ledger", raise_if_not_found=False)
        if general_ledger:
            return self._get_account_ledger_action(account, date)
        # Fallback: journal items filtered by account and date.
        domain = [("account_id", "=", account.id), ("parent_state", "=", "posted")]
        if date:
            domain.append(("date", "<=", date))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Journal Items - %(account)s", account=account.display_name),
            "res_model": "account.move.line",
            "domain": domain,
            "views": [(False, "list"), (False, "form")],
            "context": {"search_default_group_by_account": 1},
        }

    def _get_account_ledger_action(self, account, date=False):
        """General Ledger action scoped to the account and the report date, following
        enterprise's own pattern
        (``account_journal_dashboard.action_open_bank_balance_in_gl``).

        The action's ``context`` carries ``report_id``, which the ``account_reports``
        client action reads to know which report to open
        (``AccountReportController.setup``: ``this.action.context.report_id``). It has
        to be MERGED into: replacing it leaves the General Ledger with no ``report_id``
        and the view breaks on open. The account is scoped with
        ``default_filter_accounts`` (the report's own accounts filter, by code) and the
        date through the report ``options``, since the General Ledger looks at neither
        ``search_default_*`` nor ``date_to`` from the context.
        """
        action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_general_ledger")
        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = literal_eval(action_context)
        action["context"] = dict(action_context, default_filter_accounts=account.code)
        if date:
            gl_report = self.env.ref("account_reports.general_ledger_report", raise_if_not_found=False)
            if gl_report:
                # The General Ledger is a range report: a 'single' cut-off takes it to
                # date_to = report date and date_from = start of the fiscal year (see
                # ``_init_options_date``), with the previous balance on its own initial
                # balance line.
                options = gl_report.get_options({"date": {"mode": "single", "filter": "custom", "date_to": date}})
                action["params"] = {"options": options, "ignore_session": True}
        return action

    @api.model
    def action_open_variation_stock_moves(self, account_id, date=False, filters=None):
        """Variation to the unaccounted stock moves booked to that account.

        Same scope as the variation's Stock Moves component: products whose valuation
        account is the one on the line, done moves inside the valued perimeter, with no
        entry and up to the report date. Honours the report's active filters."""
        company, products, account = self._get_drilldown_scope(account_id, date, filters)
        if not products:
            return self._empty_drilldown_action("stock.move", account)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Unaccounted Stock Moves - %(account)s", account=account.display_name),
            "res_model": "stock.move",
            "domain": list(self._get_variation_stock_moves_domain(company, products, date)),
            "views": [
                (self.env.ref("stock_account.stock_move_view_list_valuation").id, "list"),
                (False, "form"),
            ],
            "context": {"search_default_groupby_product_id": 1},
        }

    @api.model
    def action_open_variation_product_values(self, account_id, date=False, filters=None):
        """Variation to the unaccounted value adjustments (``product.value``) of the
        products booked to that account. It is the other origin of the variation: cost
        changes on the product and manual adjustments of a move's value."""
        company, products, account = self._get_drilldown_scope(account_id, date, filters)
        if not products:
            return self._empty_drilldown_action("product.value", account)
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Unaccounted Value Adjustments - %(account)s", account=account.display_name),
            "res_model": "product.value",
            "domain": list(self._get_variation_product_values_domain(company, products, date)),
            "views": [(False, "list"), (False, "form")],
        }

    # -- Drill-down domains (shared with the three-dots menu count) -------------
    def _get_variation_stock_moves_domain(self, company, products, date):
        """Unaccounted moves of those products, inside the valued perimeter and up to
        the report date."""
        domain = self._get_unaccounted_moves_base_domain(company, products, date)
        return domain & self._get_valued_directions_domain()

    def _get_variation_product_values_domain(self, company, products, date):
        """Unaccounted value adjustments of those products, up to the report date. An
        adjustment points either at the product (price change) or at one of its moves
        (move value adjustment)."""
        domain = Domain(
            [
                ("account_move_id", "=", False),
                ("company_id", "=", company.id),
            ]
        ) & (Domain([("product_id", "in", products.ids)]) | Domain([("move_id.product_id", "in", products.ids)]))
        if date:
            domain &= Domain([("date", "<=", date)])
        return domain

    def _add_variation_drilldown_types(self, data, date, filters):
        """Flag on each variation line which drill-downs have records to show, under the
        ``drilldown_types`` key.

        A line with none gets no three-dots menu from the client action: nothing to show,
        no menu. That is the case of the counterpart account line —which shows up in the
        section because the variation entry has two legs
        (``_prepare_inventory_aml_vals``) but has no products booked to it— and also of a
        valuation account whose difference has no pending detail left.
        """
        lines = (data.get("stock_variation") or {}).get("lines") or []
        if not lines:
            return
        company = self.env.company
        date = self._normalize_report_date(date)
        products_by_account = self._get_products_by_valuation_account(company, date, filters)
        no_products = self.env["product.product"]
        for line in lines:
            account = self.env["account.account"].browse(line["account_id"])
            products = products_by_account.get(account, no_products)
            line["drilldown_types"] = self._get_variation_drilldown_types(company, products, date)

    def _get_variation_drilldown_types(self, company, products, date):
        """Drill-down types with at least one record for that account.

        The count runs in ``sudo``: the report is read by accounting users, who may have
        no read access on ``stock.move``, and an ``AccessError`` here would break the
        whole report. Access is evaluated as usual when the action is opened.
        """
        if not products:
            return []
        available = []
        for line_type, model, get_domain in self._get_drilldown_checks():
            domain = get_domain(company, products, date)
            if self.env[model].sudo().search_count(list(domain), limit=1):
                available.append(line_type)
        return available

    def _get_drilldown_checks(self):
        """``(line_type, model, domain getter)`` of every origin the variation drills down
        to. A method so a module adding an origin extends the list instead of rewriting
        ``_get_variation_drilldown_types``; keep it aligned with ``_get_valid_line_types``
        and with the ``_variationDrilldowns`` map on the JS side."""
        return [
            (LINE_TYPE_STOCK_MOVE, "stock.move", self._get_variation_stock_moves_domain),
            (LINE_TYPE_PRODUCT_VALUE, "product.value", self._get_variation_product_values_domain),
        ]

    def _get_drilldown_scope(self, account_id, date, filters):
        """Company, products and account of the drill-down. The products are the
        report's, with the active filters applied, narrowed down to the ones whose
        valuation account is THAT one."""
        company = self.env.company
        account = self.env["account.account"].browse(int(account_id)).exists()
        if not account:
            raise UserError(self.env._("The account no longer exists."))
        date = self._normalize_report_date(date)
        products_by_account = self._get_products_by_valuation_account(company, date, filters)
        scoped = products_by_account.get(account, self.env["product.product"])
        return company, scoped, account

    def _get_products_by_valuation_account(self, company, date, filters):
        """The report's products grouped by their valuation account.

        Resolved once per call: the three-dots count needs the scope of EVERY line, and
        recomputing the products line by line would be the same search over and over.
        """
        filters = filters or {}
        products = self._get_filtered_valued_products(
            company,
            date,
            filters.get("product_ids"),
            filters.get("categ_ids"),
            filters.get("cost_methods"),
            filters.get("valuations"),
        )
        accounts_by_product = company._get_accounts_by_product(products=products) if products else {}
        products_by_account = {}
        for product, accounts in accounts_by_product.items():
            account = accounts.get("valuation")
            if not account:
                continue
            products_by_account[account] = products_by_account.get(account, self.env["product.product"]) | product
        return products_by_account

    def _get_report_accounting_data(self, company, accounts_by_product, products, at_date, product_scope):
        """Booked value per valuation account: the Initial Balance the report starts from.

        With a product filter on, only what is attributable to THOSE products: several
        products share a valuation account, so the whole account balance would drag in
        the value already booked for the other ones (task 64440).

        Without it, the standard's account balance, portion with no product included: the
        Movement Type filter scopes no product, and dropping the no-product balance there
        would break the starting point of the breakdown per origin.

        Shared with the closing entry (``res.company``), which has to book exactly the
        variation the report shows.
        """
        if product_scope:
            return company._get_attributable_accounting_value(
                self._get_valuation_accounts(accounts_by_product), products, at_date=at_date or None
            )
        return company.stock_accounting_value(accounts_by_product, at_date=at_date or None)

    def _get_valuation_accounts(self, accounts_by_product):
        """Valuation accounts involved in that set of products."""
        return self.env["account.account"].browse(
            {accounts["valuation"].id for accounts in accounts_by_product.values() if accounts.get("valuation")}
        )

    def _normalize_report_date(self, date):
        """Cut-off date as the report handles it: ``date``, or ``False`` when it is
        today (the standard treats today as no cut-off)."""
        if isinstance(date, str):
            date = fields.Date.from_string(date)
        if date == fields.Date.context_today(self):
            return False
        return date

    def _empty_drilldown_action(self, res_model, account):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("No records - %(account)s", account=account.display_name),
            "res_model": res_model,
            "domain": [("id", "=", False)],
            "views": [(False, "list"), (False, "form")],
        }

    # -- Filtering helpers -----------------------------------------------------
    def _empty_valuation_report_data(self, company):
        """A report at zero, for a filter matching no product, with the shape the client
        action expects."""
        return {
            "company_id": company.id,
            "currency_id": company.currency_id.id,
            "ending_stock": {"label": _("Ending Stock"), "value": 0, "lines_by_account_id": {}},
            "initial_balance": {"label": _("Initial Balance"), "value": 0, "lines_by_account_id": {}},
            "stock_variation": {"label": _("Stock Variation"), "value": 0, "lines": []},
            "accounts_by_id": {},
        }

    def _normalize_line_types(self, line_types):
        """Keep the valid types only. Both of them (or none that is useful) means no
        Movement Type filter at all."""
        if not line_types:
            return []
        valid = self._get_valid_line_types()
        selected = [lt for lt in line_types if lt in valid]
        if set(selected) >= set(valid):
            return []
        return selected

    def _get_valid_line_types(self):
        """The origins the variation can be broken down into. A method and not the module
        constant so a third origin can be added by inheritance — a currency revaluation,
        for one (task 58212) — without rewriting ``_normalize_line_types``. Keep it aligned
        with ``_get_drilldown_checks`` and with ``lineTypeOptions`` on the JS side."""
        return VALID_LINE_TYPES

    def _get_filtered_valued_products(self, company, date, product_ids, categ_ids, cost_methods, valuations):
        """The standard ``valued_products`` search plus the product/category domain, and
        the costing method / valuation type filtered in Python (compute fields with no
        usable ``search``)."""
        # sudo and valuation context as in the standard: ``qty_available`` expands kit
        # BoMs that an accounting user cannot read.
        valued_product_context = self.env["product.product"].sudo().with_company(company)._with_valuation_context()
        if date:
            valued_product_context = valued_product_context.with_context(at_date=date, to_date=date)
        domain = Domain(
            [
                ("is_storable", "=", True),
            ]
        ) & (Domain([("qty_available", "!=", 0)]) | Domain([("lot_valuated", "=", True)]))
        domain &= self._get_valuation_report_extra_domain(product_ids, categ_ids)
        valued_products = valued_product_context.search(domain)

        # ``cost_method`` is a compute with no search, and ``valuation.search`` only
        # takes ``=`` with a single value, hence the filtering in Python. Reading the
        # fields keeps the fallback to the company defaults when the category has no
        # property set.
        if cost_methods:
            valued_products = valued_products.filtered(lambda p: p.cost_method in cost_methods)
        if valuations:
            valued_products = valued_products.filtered(lambda p: p.valuation in valuations)
        return valued_products

    def _get_valuation_report_extra_domain(self, product_ids, categ_ids):
        """Extra ``product.product`` domain for the Product and Category filters, the
        latter including subcategories via ``child_of``."""
        domain = Domain.TRUE
        if product_ids:
            domain &= Domain([("id", "in", product_ids)])
        if categ_ids:
            domain &= Domain([("categ_id", "child_of", categ_ids)])
        return domain

    # -- Movement Type filter (breakdown of the variation) ---------------------
    def _get_valuation_report_variation_components(
        self, company, products, accounts_by_product, at_date, line_types, inventory_data, accounting_data
    ):
        """The filtered component of the variation, as AML vals.

        Returns the same structure as ``res.company._get_stock_valuation_account_vals``,
        so both the report section and the per-origin closing entry consume it unchanged.
        """
        balances_by_account = self._get_variation_balances_by_account(
            company, products, accounts_by_product, at_date, line_types, inventory_data, accounting_data
        )
        return self._get_variation_aml_vals(company, balances_by_account)

    def _get_variation_balances_by_account(
        self, company, products, accounts_by_product, at_date, line_types, inventory_data, accounting_data
    ):
        """Balance of the filtered component, per valuation account. The two components
        add up to the native total variation, to the cent:

        - ``stock_move``: what the unaccounted, non-revalued physical moves contribute,
          taken from ``stock.move.value`` (in adds, out subtracts).
        - ``product_value``: the REMAINDER, i.e. total variation minus the stock
          component. Taking it as a remainder is what catches every revaluation: the ones
          with ``move_id`` (a move revalued) and the ones without (standard price or lot
          price changes, which store the new unit price and not a delta, so they cannot
          be added up directly), plus location reclassifications and FIFO/AVCO rounding.

        Kept apart from the conversion to AML vals because the balances also feed the
        projected Ending Stock and the per-origin closing entry (``res.company``).
        """
        stock_move_balance = self._get_unaccounted_move_balances(
            company, products, accounts_by_product, at_date, [LINE_TYPE_STOCK_MOVE]
        )
        if line_types == [LINE_TYPE_STOCK_MOVE]:
            return stock_move_balance
        total_balance = self._get_total_variation_balance(company, at_date, inventory_data, accounting_data)
        balances_by_account = defaultdict(float)
        for account in set(total_balance) | set(stock_move_balance):
            balances_by_account[account] = total_balance.get(account, 0) - stock_move_balance.get(account, 0)
        return balances_by_account

    def _get_variation_aml_vals(self, company, balances_by_account):
        """Turn the balances per account into AML vals, with the valuation account and its
        counterpart as the standard does."""
        vals_list = []
        for account, balance in balances_by_account.items():
            if company.currency_id.is_zero(balance):
                continue
            account_variation = account.account_stock_variation_id or company.expense_account_id
            if not account_variation:
                continue
            vals_list += company._prepare_inventory_aml_vals(
                account,
                account_variation,
                balance,
                _("Stock Variation (filtered)"),
            )
        return vals_list

    def _get_total_variation_balance(self, company, at_date, inventory_data, accounting_data, extra_aml_vals_list=None):
        """Net variation per valuation account, replicating the standard computation in
        ``res.company._get_stock_valuation_account_vals``: inventory value minus booked
        value, net of the location reclassifications (``_get_location_valuation_vals``).
        It is the base of the Product Value remainder.

        ``extra_aml_vals_list`` is the vals already built by the caller whose balance has
        to be netted; the closing passes the ones of its own entry instead of having them
        searched again.
        """
        if extra_aml_vals_list is None:
            extra_aml_vals_list = company._get_location_valuation_vals(at_date)
        extra_balance = company._get_extra_balance(extra_aml_vals_list)
        total_balance = defaultdict(float)
        for account in set(inventory_data) | set(accounting_data):
            total_balance[account] = (
                inventory_data.get(account, 0) - accounting_data.get(account, 0) - extra_balance.get(account.id, 0)
            )
        return total_balance

    def _get_unaccounted_move_balances(
        self, company, products, accounts_by_product, at_date, line_types, by_product=None
    ):
        """Net value variation per valuation account contributed by the unaccounted
        ``stock.move`` records, replicating the in/out logic of
        ``res.company._get_location_valuation_vals``: valued incoming moves (``is_in``,
        destination in a valued location) add and valued outgoing ones (``is_out``,
        origin in a valued location) subtract. ``value`` is always positive; the
        direction gives the sign.

        The valuation account is resolved PER PRODUCT from ``accounts_by_product`` —the
        one the three sections use— and not from the category property, so it also works
        when the account is set on the product and neither on
        ``category.property_stock_valuation_account_id`` nor on the company.

        Pass ``by_product`` (an accumulator dict) to get the same balance broken down per
        ``(account, product)``, which the per-origin closing needs to attribute its lines.
        """
        Move = self.env["stock.move"].sudo()
        valued_locations = self.env["stock.location"].sudo().search([("is_valued_internal", "=", True)])
        if not (products and valued_locations):
            return {}

        account_by_product_id = {
            product.id: accounts["valuation"]
            for product, accounts in accounts_by_product.items()
            if accounts.get("valuation")
        }

        base_domain = self._get_unaccounted_moves_base_domain(company, products, at_date)
        base_domain &= self._get_line_type_move_domain(products, line_types)

        account_balance = defaultdict(float)
        directions = (
            # (sign, direction domain)
            (1, Domain([("is_in", "=", True), ("location_dest_id", "in", valued_locations.ids)])),
            (-1, Domain([("is_out", "=", True), ("location_id", "in", valued_locations.ids)])),
        )
        # What a move contributes is its ``value`` (see
        # ``stock.move._get_inventory_value``), the criterion the inventory is valued
        # with in the three costing methods, so it is aggregated with one _read_group per
        # direction instead of walking move by move.
        for sign, direction_domain in directions:
            grouped = Move._read_group(
                base_domain & direction_domain,
                ["product_id"],
                self._get_unaccounted_move_aggregates(),
            )
            for product, *aggregates in grouped:
                account = account_by_product_id.get(product.id)
                if account:
                    self._accumulate_move_balance(account, product, sign, aggregates, account_balance, by_product)
        return account_balance

    def _get_unaccounted_move_aggregates(self):
        """Aggregate specs read per product to build the variation.

        The FIRST one is what a move contributes to the balance in company currency (see
        ``stock.move._get_inventory_value``). A module needing another amount —the same
        moves valued in a second currency, task 58212— appends its spec here and reads it
        back in ``_accumulate_move_balance``, instead of running the ``_read_group`` a
        second time over the same domain.
        """
        return ["value:sum"]

    def _accumulate_move_balance(self, account, product, sign, aggregates, account_balance, by_product):
        """Add one grouped row to the accumulators. ``aggregates`` arrives in the order of
        ``_get_unaccounted_move_aggregates``; ``sign`` is +1 for incoming moves and -1 for
        outgoing ones."""
        value = aggregates[0]
        account_balance[account] += sign * value
        if by_product is not None:
            by_product[account.id, product.id] += sign * value

    def _get_unaccounted_move_balances_by_product(self, company, products, accounts_by_product, at_date, line_types):
        """``_get_unaccounted_move_balances`` broken down per ``(account, product)``."""
        by_product = defaultdict(float)
        self._get_unaccounted_move_balances(
            company, products, accounts_by_product, at_date, line_types, by_product=by_product
        )
        return by_product

    def _get_line_type_deltas_by_product(self, company, products, accounts_by_product, at_date, line_types):
        """What the filtered origin contributes per ``(account, product)``, so that a
        closing filtered by Movement Type is attributed per product as the full one is.

        - ``stock_move``: comes from the moves, which already carry a product, so the
          attribution is exact and leaves no remainder.
        - ``product_value``: the REMAINDER, with the same criterion as the report section
          — the product's pending difference minus what its moves contribute. What is
          attributable to no product (the booked balance with no product) stays out, and
          the split's no-product line nets it.
        """
        stock_by_product = self._get_unaccounted_move_balances_by_product(
            company, products, accounts_by_product, at_date, [LINE_TYPE_STOCK_MOVE]
        )
        if line_types == [LINE_TYPE_STOCK_MOVE]:
            return stock_by_product
        products_by_account = company._get_products_by_valuation_account(accounts_by_product)
        pending = company._get_pending_valuation_deltas(products_by_account, at_date)
        return {key: balance - stock_by_product.get(key, 0.0) for key, balance in pending.items()}

    def _get_unaccounted_moves_base_domain(self, company, products, at_date):
        """Done moves of those products, still unaccounted and up to the cut-off date.
        Common base of the variation computation and of the drill-down; the caller adds
        the in/out direction."""
        domain = Domain(
            [
                ("related_account_move_id", "=", False),
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("state", "=", "done"),
            ]
        )
        if at_date:
            domain &= Domain([("date", "<=", at_date)])
        return domain

    def _get_valued_directions_domain(self):
        """Moves inside the valued perimeter, in either direction."""
        valued_locations = self.env["stock.location"].sudo().search([("is_valued_internal", "=", True)])
        return Domain([("is_in", "=", True), ("location_dest_id", "in", valued_locations.ids)]) | Domain(
            [("is_out", "=", True), ("location_id", "in", valued_locations.ids)]
        )

    def _get_line_type_move_domain(self, products, line_types):
        """Narrow the Stock Moves component down to the NON revalued physical moves: a
        revalued ``stock.move`` stays out, taken by the Product Value remainder. Only
        called with ``[stock_move]``; any other case restricts nothing."""
        if line_types != [LINE_TYPE_STOCK_MOVE]:
            return Domain.TRUE
        reval_move_ids = self._get_revalued_move_ids(products)
        # With no revaluations, every move is a Stock Move.
        return Domain([("id", "not in", reval_move_ids)]) if reval_move_ids else Domain.TRUE

    def _get_revalued_move_ids(self, products):
        """Moves of those products carrying an adjustment that CHANGED their value.

        Split from the domain so the criterion —``_is_revaluation``— can be refined
        without touching the query, and so a module can widen the search."""
        product_values = (
            self.env["product.value"]
            .sudo()
            .search(
                [
                    ("move_id", "!=", False),
                    ("move_id.product_id", "in", products.ids),
                ]
            )
        )
        return product_values.filtered(self._is_revaluation).move_id.ids

    def _is_revaluation(self, product_value):
        """Does this adjustment take its move out of the Stock Moves component?

        Only if it moved the value IN COMPANY CURRENCY. Merely pointing at a move is not
        enough: a module can record an adjustment that leaves ``value`` untouched —a
        secondary-currency correction, task 58212— and excluding that move would hand its
        whole value to the Product Value remainder without anything having changed. The
        total still adds up, because that remainder is a residue, so the breakdown would
        lie in silence.

        Compared with the currency's own rounding, not against ``0``. An adjustment with
        no ``previous_value`` (recorded before that field existed) reads as a delta equal
        to the new value, so it counts as a revaluation: the conservative side, and the
        behaviour there has always been.
        """
        currency = product_value.company_id.currency_id
        return not currency.is_zero(product_value.delta)
