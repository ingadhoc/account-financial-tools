from collections import defaultdict

from odoo import fields, models
from odoo.fields import Domain

from ..report.stock_valuation_report import LINE_TYPE_PRODUCT_VALUE, LINE_TYPE_STOCK_MOVE

# Context key scoping the closing to a set of products (partial closing).
CLOSING_PRODUCT_CTX = "stock_valuation_closing_product_ids"
# Context key scoping the closing to one origin of the variation (stock moves or
# value adjustments), as per the Movement Type filter.
CLOSING_LINE_TYPES_CTX = "stock_valuation_closing_line_types"
# Context key asking for the valuation lines to be split per product. Set by the
# closing, which WRITES the entry; reading the report does not need it, as its
# sections are aggregated per account.
SPLIT_BY_PRODUCT_CTX = "stock_valuation_split_by_product"


class ResCompany(models.Model):
    _inherit = "res.company"

    def action_close_stock_valuation(
        self,
        at_date=None,
        auto_post=False,
        product_ids=None,
        categ_ids=None,
        cost_methods=None,
        valuations=None,
        line_types=None,
    ):
        """Link the periodic closing entry to the ``stock.move`` records it values,
        and honour the report filters.

        Out of the box the closing is aggregated per account and linked to no move, so
        from the moves lists there was no way to reach the entry that valued them.
        Storing it in the standard ``account_move_id`` makes the navigable
        ``related_account_move_id``, the Booked / Not Booked filters and the search bar
        behave the same for periodic and perpetual valuation.

        Filters (task 64440):

        - Product / Category / Method / Valuation Type: PARTIAL closing limited to
          those products; the rest stays open.
        - Movement Type (``line_types``): closing limited to that ORIGIN of the
          variation, leaving the other one pending. Selecting both (or none) closes
          everything. The two origins add up to the full closing, and each entry links
          only the records it booked, so whatever stays open keeps showing up in the
          report's variation.

        Caveat, same as the report: the portion of the account's booked balance that
        carries NO product (closings posted before this module, the standard's location
        reclassifications, entries an accountant posts by hand) cannot be claimed by a
        product filter on its own, so a partial closing takes an ESTIMATED share of it —
        its weight in the pending gap, see ``_get_unattributed_accounting_share``.
        Closing every product of the account adds up to exactly the full closing, but
        each partial closing on its own is an approximation of that portion.
        """
        self.ensure_one()
        report = self.env["stock_account.stock.valuation.report"]
        line_types = report._normalize_line_types(line_types)
        if line_types:
            self = self.with_context(**{CLOSING_LINE_TYPES_CTX: line_types})
        # Partial closing: scope it to the products matching the filters.
        if any([product_ids, categ_ids, cost_methods, valuations]):
            date = fields.Date.from_string(at_date) if isinstance(at_date, str) else at_date
            if date == fields.Date.context_today(self):
                date = False
            products = report._get_filtered_valued_products(
                self, date, product_ids, categ_ids, cost_methods, valuations
            )
            self = self.with_context(**{CLOSING_PRODUCT_CTX: products.ids})
        action = super().action_close_stock_valuation(at_date=at_date, auto_post=auto_post)
        closing_move = self.env["account.move"]
        if isinstance(action, dict) and action.get("res_model") == "account.move":
            closing_move = self.env["account.move"].browse(action.get("res_id")).exists()
        if not closing_move:
            return action
        # Each closing links ONLY the records it actually booked. With the Movement
        # Type filter a single origin is booked, so the other one cannot be marked as
        # booked: its portion would vanish from the pending variation with no entry.
        booked_line_types = self.env.context.get(CLOSING_LINE_TYPES_CTX) or []
        books_moves = LINE_TYPE_PRODUCT_VALUE not in booked_line_types
        books_product_values = LINE_TYPE_STOCK_MOVE not in booked_line_types
        if books_moves:
            moves = self._get_periodic_closing_stock_moves(at_date)
            # Leave alone moves that already have a posted entry (perpetual ones, or a
            # valid previous closing); do re-link the ones whose entry was left
            # unposted, e.g. a cancelled and regenerated closing.
            moves = moves.filtered(lambda m: not m.account_move_id or m.account_move_id.state != "posted")
            if booked_line_types:
                # The Stock Moves component leaves revalued moves out (the other origin
                # takes their value), so they are not linked either.
                revalued = self.env["product.value"].sudo().search([("move_id", "in", moves.ids)]).move_id
                moves -= revalued
            if moves:
                moves.account_move_id = closing_move.id
        # Value adjustments (``product.value``) are booked by this closing too. Out of
        # the box they keep no reference to the entry, so a cost change was booked
        # leaving no trace on the adjustment nor on the revalued move, which still
        # points at its original entry.
        if books_product_values:
            product_values = self._get_periodic_closing_product_values(at_date)
            if product_values:
                product_values.account_move_id = closing_move.id
        return action

    def _get_stock_valuation_account_vals(self, accounts_by_product, at_date=None, extra_aml_vals_list=None):
        """Book the valuation leg with one line per product.

        The standard closing aggregates per account with ``product_id = False``, so
        its balance cannot be attributed: filtering the report's Initial Balance by
        product would still show the whole account balance. The split keeps amount,
        counterpart and account balance untouched (see
        ``_split_valuation_vals_by_product``), and leaves each product booked at its
        inventory value.
        """
        vals_list = super()._get_stock_valuation_account_vals(
            accounts_by_product, at_date=at_date, extra_aml_vals_list=extra_aml_vals_list
        )
        vals_list = self._annotate_valuation_vals(vals_list, accounts_by_product, at_date=at_date)
        if not self.env.context.get(SPLIT_BY_PRODUCT_CTX):
            return vals_list
        return self._split_valuation_vals_by_product(vals_list, accounts_by_product, at_date)

    def _annotate_valuation_vals(self, vals_list, accounts_by_product, at_date=None):
        """Hook: add keys to the closing vals BEFORE they are split per product.

        The vals are born in the standard ``_prepare_inventory_aml_vals``, which knows
        nothing beyond account, balance and label, so a module needing another amount on
        the line has nowhere to put it. Here it does, and ``_get_valuation_val_extra_vals``
        then prorates whatever was added when the line is split per product — that hook
        expects the amount to be on the vals already, which is what this one is for
        (task 58212, ``stock_currency_valuation``: ``amount_currency``).

        Returns the list, so an override may replace the vals rather than only mutate them.
        """
        return vals_list

    def _split_valuation_vals_by_product(self, vals_list, accounts_by_product, at_date=None, deltas_by_product=None):
        """Split the valuation leg of each pair of vals into one line per product.

        Vals come in pairs, as ``_prepare_inventory_aml_vals`` returns the valuation
        leg plus its counterpart, so they are walked two by two and only the
        valuation one is split. A pair that cannot be told apart is left as is,
        rather than attributed wrongly: an odd number of vals, or both legs being
        valuation accounts (one account's counterpart is another product's valuation
        account).

        ``deltas_by_product`` is what each ``(account, product)`` takes. The full
        closing uses the default, each product's pending difference; a closing
        filtered by Movement Type passes the contribution of that origin, which is
        all that entry books.
        """
        products_by_account = self._get_products_by_valuation_account(accounts_by_product)
        if not products_by_account or len(vals_list) % 2:
            return vals_list
        if deltas_by_product is None:
            deltas_by_product = self._get_pending_valuation_deltas(products_by_account, at_date)
        account_by_id = {account.id: account for account in products_by_account}
        split_vals = []
        for first, second in zip(vals_list[::2], vals_list[1::2], strict=True):
            valuation_vals = [vals for vals in (first, second) if vals["account_id"] in account_by_id]
            if len(valuation_vals) != 1:
                split_vals += [first, second]
                continue
            for vals in (first, second):
                if vals is valuation_vals[0]:
                    account = account_by_id[vals["account_id"]]
                    split_vals += self._get_valuation_vals_by_product(
                        vals, account, products_by_account[account], deltas_by_product
                    )
                else:
                    split_vals.append(vals)
        return split_vals

    def _get_products_by_valuation_account(self, accounts_by_product):
        products_by_account = {}
        for product, accounts in accounts_by_product.items():
            account = accounts.get("valuation")
            if account:
                products_by_account[account] = products_by_account.get(account, self.env["product.product"]) | product
        return products_by_account

    def _get_pending_valuation_deltas(self, products_by_account, at_date=None):
        """Each product's pending difference: its inventory value minus the balance
        already attributed to it."""
        accounting_by_product = self._get_stock_accounting_value_by_product(
            self.env["account.account"].browse([account.id for account in products_by_account]), at_date
        )
        deltas = {}
        for account, products in products_by_account.items():
            for product in products:
                key = (account.id, product.id)
                # Same value criterion as ``stock_value``.
                inventory_value = product.with_context(to_date=at_date).total_value
                deltas[key] = inventory_value - accounting_by_product.get(key, 0.0)
        return deltas

    def _get_valuation_vals_by_product(self, vals, account, products, deltas_by_product):
        """One line per product plus a no-product line for what is left unattributed.

        The net of the lines equals the net of the original vals, which is what keeps
        the entry balanced whatever the deltas are.

        Everything is ROUNDED to the currency precision and the residual absorbs the
        rounding, so the split adds up to the very cent the counterpart leg is booked at.
        Leaving it to float and rounding each line on its own unbalanced the entry on a
        half cent: a net of 72.725 against lines of 100 and -27.275 rounds to 72.73
        against 100 - 27.28 = 72.72, and ``account.move`` refuses it.
        """
        net = self.currency_id.round(vals["debit"] - vals["credit"])
        assigned = 0.0
        product_vals = []
        for product in products:
            delta = self.currency_id.round(deltas_by_product.get((account.id, product.id), 0.0))
            if self.currency_id.is_zero(delta):
                continue
            product_vals.append(self._get_valuation_val(vals, delta, product.id, net=net))
            assigned += delta
        residual = self.currency_id.round(net - assigned)
        if not self.currency_id.is_zero(residual):
            product_vals.append(self._get_valuation_val(vals, residual, False, net=net))
        return self._balance_valuation_extra_vals(vals, product_vals) or [vals]

    def _balance_valuation_extra_vals(self, vals, product_vals):
        """Hook: reconcile the amounts a child put on the split against the vals they
        were split from, once the whole split is known.

        ``_get_valuation_val_extra_vals`` shares an amount out line by line and cannot see
        what the other lines were rounded to, so the shares can miss the total by a cent.
        For ``debit`` / ``credit`` the residual absorbs exactly that; an amount the child
        added has no equivalent, and nothing else would catch it: the entry still balances
        in company currency, so it posts (task 58212, ``stock_currency_valuation``:
        ``amount_currency``).

        Returns the list, so an override may replace the vals rather than only mutate them.
        """
        return product_vals

    def _get_valuation_val(self, vals, balance, product_id, net=None):
        """One line of the split, with the product named in the LABEL as well.

        The valuation account is the category's, so in a global entry several lines
        share it and the standard label —the same for all of them— gave the user no way
        to tell which line belongs to which product. The counterpart keeps the generic
        label: it is not attributed to any product (functional feedback, task 64440).
        """
        product = self.env["product.product"].browse(product_id) if product_id else None
        name = vals.get("name")
        if product and name:
            name = self.env._("%(label)s - %(product)s", label=name, product=product.display_name)
        return dict(
            vals,
            name=name,
            debit=balance if balance > 0 else 0.0,
            credit=-balance if balance < 0 else 0.0,
            product_id=product_id,
            **self._get_valuation_val_extra_vals(vals, balance, net),
        )

    def _get_valuation_val_extra_vals(self, vals, balance, net):
        """Hook: the amounts of a line that are NOT ``debit`` / ``credit``.

        Only those two are re-split here; every other key of ``vals`` is copied verbatim
        onto EVERY line, which is right for the account, the counterpart or the label, and
        WRONG for an amount. A module adding one has to prorate it the same way the balance
        is, or the entry adds up in the company currency and not in the other one. The
        ``amount_currency`` of a secondary-currency valuation is the case this exists for
        (task 58212, ``stock_currency_valuation``):

            def _get_valuation_val_extra_vals(self, vals, balance, net):
                res = super()._get_valuation_val_extra_vals(vals, balance, net)
                if vals.get("amount_currency") and net:
                    res["amount_currency"] = vals["amount_currency"] * balance / net
                return res

        ``net`` is the net of the vals being split, i.e. the denominator of the share
        (``None`` when the caller does not split).
        """
        return {}

    def _get_stock_accounting_value_by_product(self, accounts, at_date=None, products=None):
        """Booked balance per ``(valuation account, product)``. Journal items with no
        product are out: they are the ones to attribute."""
        self.ensure_one()
        domain = Domain(
            [
                ("account_id", "in", accounts.ids),
                ("company_id", "=", self.id),
                ("parent_state", "=", "posted"),
            ]
        )
        domain &= Domain(
            [("product_id", "in", products.ids)] if products is not None else [("product_id", "!=", False)]
        )
        if at_date:
            domain &= Domain([("date", "<=", at_date)])
        return {
            (account.id, product.id): balance
            for account, product, balance in self.env["account.move.line"]._read_group(
                domain, ["account_id", "product_id"], ["balance:sum"]
            )
        }

    def _get_attributable_accounting_value(self, accounts, products, at_date=None):
        """Booked balance attributable to those products, per valuation account. It is
        the Initial Balance while a product filter is active.

        Deliberately NOT an override of ``stock_accounting_value``: other modules
        reimplement that method without calling ``super()``
        (``stock_account_multicompany_ux`` rewrites it for the branches model), so the
        product filter was silently lost depending on which modules were installed.
        The report asks for this one explicitly instead of relying on the MRO.

        The portion booked with ``product_id = False`` is shared out over the products
        of the account (see ``_get_unattributed_accounting_share``) instead of being
        dropped. Dropping it broke the report: filtering product by product reported
        MORE left to book than the unfiltered report did, by exactly that portion, and
        closing each product in turn would have booked it twice (task 64440).
        """
        self.ensure_one()
        account_data = defaultdict(float)
        by_product = self._get_stock_accounting_value_by_product(accounts, at_date, products=products)
        accounts_by_id = {account.id: account for account in accounts}
        for (account_id, _product_id), balance in by_product.items():
            account_data[accounts_by_id[account_id]] += balance
        # Only reached while there IS an unattributed portion. On a base whose closings
        # all ran through this module there is none, so this costs nothing.
        unattributed = self._get_unattributed_accounting_value(accounts, at_date)
        if unattributed:
            products_by_account = self._get_valued_products_by_account(
                self.env["account.account"].browse([account.id for account in unattributed])
            )
            for account, balance in unattributed.items():
                share = self._get_unattributed_accounting_share(
                    account, products_by_account.get(account), products, at_date
                )
                if share:
                    account_data[account] += balance * share
        return account_data

    def _get_unattributed_accounting_value(self, accounts, at_date=None):
        """Booked balance of each valuation account that carries NO product, i.e. the
        portion no product filter can claim on its own.

        Where it comes from: closings posted before this module (the standard books the
        variation aggregated per account, with ``product_id = False``), the location
        reclassifications of the standard closing, the residual line of the per-product
        split, and any entry an accountant posts by hand on the account.
        """
        self.ensure_one()
        domain = Domain(
            [
                ("account_id", "in", accounts.ids),
                ("company_id", "=", self.id),
                ("parent_state", "=", "posted"),
                ("product_id", "=", False),
            ]
        )
        if at_date:
            domain &= Domain([("date", "<=", at_date)])
        return {
            account: balance
            for account, balance in self.env["account.move.line"]._read_group(domain, ["account_id"], ["balance:sum"])
            if not self.currency_id.is_zero(balance)
        }

    def _get_valued_products_by_account(self, accounts):
        """Every valued product of the company hanging from each of those valuation
        accounts. It is the universe the unattributed portion is shared out over, so it
        cannot be the filtered set."""
        self.ensure_one()
        products_by_account = {}
        for product, product_accounts in self._get_accounts_by_product().items():
            account = product_accounts.get("valuation")
            if not account or account not in accounts:
                continue
            products_by_account[account] = products_by_account.get(account, self.env["product.product"]) | product
        return products_by_account

    def _get_unattributed_accounting_share(self, account, account_products, products, at_date=None):
        """Share of the account's unattributed balance that the filtered products take.

        Criterion: their weight in the account's PENDING GAP, each product's inventory
        value minus what is already booked for it (``_get_pending_valuation_deltas``, the
        very figure the closing books). It is an estimate —the journal item records no
        product, so there is nothing exact to recover— but it is the rule that keeps the
        report coherent, and the weight has to be the gap rather than the plain inventory
        value: a product already booked at its inventory value has no gap left and must
        claim nothing, otherwise closing the products one by one re-shares the leftover
        over the ones already closed and books more than the full closing does.

        Filtering by every product of the account adds up to 1, so the filtered report
        matches the unfiltered one whatever the split.

        When the account has no pending gap at all (everything booked, and the leftover is
        a balance to be written off) the weight falls back to the count of products, which
        preserves that same property.
        """
        self.ensure_one()
        if not account or not account_products:
            return 0.0
        in_scope = account_products & products
        if not in_scope:
            return 0.0
        deltas = self._get_pending_valuation_deltas({account: account_products}, at_date)
        total = sum(deltas.get((account.id, product.id), 0.0) for product in account_products)
        if self.currency_id.is_zero(total):
            return len(in_scope) / len(account_products)
        in_scope_gap = sum(deltas.get((account.id, product.id), 0.0) for product in in_scope)
        return in_scope_gap / total

    def _get_periodic_closing_product_values(self, at_date=None):
        """Value adjustments the closing entry books: the ones with no entry yet, or
        whose entry was left unposted (e.g. a cancelled and regenerated closing), up to
        the cut-off date.

        No lower date bound on purpose: the variation the entry closes is cumulative
        (inventory value minus booked value), so an old adjustment that was never booked
        is covered as well, not only the ones from the last period.

        Adjustments with NO variation are left out: they put nothing in the entry, so
        stamping them would claim they were booked when there was nothing to book, and
        the "no entry yet" filter —what identifies the difference still to adjust— would
        stop meaning that (functional feedback, task 64440).
        """
        self.ensure_one()
        if isinstance(at_date, str):
            at_date = fields.Date.from_string(at_date)
        domain = [
            ("company_id", "=", self.id),
            "|",
            ("account_move_id", "=", False),
            ("account_move_id.state", "!=", "posted"),
        ]
        if at_date:
            domain.append(("date", "<=", at_date))
        # Partial closing: only the adjustments of the filtered products, whether they
        # point at the product (price change) or at a move of it (move value
        # adjustment).
        closing_product_ids = self.env.context.get(CLOSING_PRODUCT_CTX)
        if closing_product_ids is not None:
            domain += [
                "|",
                ("product_id", "in", closing_product_ids),
                ("move_id.product_id", "in", closing_product_ids),
            ]
        product_values = self.env["product.value"].sudo().search(domain)
        # ``delta`` is computed, so it cannot be a domain leaf.
        return product_values.filtered(lambda value: not self.currency_id.is_zero(value.delta))

    def _get_periodic_closing_stock_moves(self, at_date=None):
        """Moves covered by the closing entry, with the same scope as
        ``_get_location_valuation_vals``: periodic products, entering or leaving valued
        locations, up to the cut-off date.

        No lower date bound, for the same reason as
        ``_get_periodic_closing_product_values``: the variation the entry closes is
        cumulative (inventory value minus booked value), so a move that a previous
        closing left out —because that closing was filtered by product or by Movement
        Type— is booked by this one whatever its date, and has to be linked to it.
        Bounding this by the previous closing date booked its value and left the move
        pointing at no entry (functional feedback, task 64440).

        Moves already booked need no bound either: they are excluded by
        ``related_account_move_id`` below and by the caller.
        """
        self.ensure_one()
        if isinstance(at_date, str):
            at_date = fields.Date.from_string(at_date)
        valued_locations = self.env["stock.location"].search(
            [
                ("company_id", "in", [self.id, False]),
            ]
        )
        if not valued_locations:
            return self.env["stock.move"]
        domain = [
            "|",
            "&",
            ("is_out", "=", True),
            ("location_dest_id", "in", valued_locations.ids),
            "&",
            ("is_in", "=", True),
            ("location_id", "in", valued_locations.ids),
            ("product_id.is_storable", "=", True),
            ("company_id", "=", self.id),
            ("related_account_move_id", "=", False),
        ]
        # Partial closing: only the moves of the filtered products.
        closing_product_ids = self.env.context.get(CLOSING_PRODUCT_CTX)
        if closing_product_ids is not None:
            domain.append(("product_id", "in", closing_product_ids))
        if at_date:
            domain.append(("date", "<=", at_date))
        return self.env["stock.move"].search(domain)

    def _action_close_stock_valuation(self, at_date=None):
        """Partial closing: when the context carries the filtered products, build the
        vals for THOSE products only, replicating the standard sequence (location
        reclassifications + stock variation + continental perpetual variation) with
        ``accounts_by_product`` and the moves scoped. Without the context key, delegate
        to the standard.

        This is also where the per-product split is requested
        (``SPLIT_BY_PRODUCT_CTX``): the entry is WRITTEN here, and the standard would
        leave it aggregated per account with no product.
        """
        self = self.with_context(**{SPLIT_BY_PRODUCT_CTX: True})
        if self.env.context.get(CLOSING_LINE_TYPES_CTX):
            return self._get_line_type_closing_vals(at_date)
        closing_product_ids = self.env.context.get(CLOSING_PRODUCT_CTX)
        if closing_product_ids is None:
            return super()._action_close_stock_valuation(at_date=at_date)
        products = self.env["product.product"].browse(closing_product_ids)
        accounts_by_product = self._get_accounts_by_product(products=products)
        aml_vals_list = []
        vals_list = self._get_location_valuation_vals(at_date)
        if vals_list:
            aml_vals_list += vals_list
        vals_list = self._get_partial_stock_variation_vals(products, accounts_by_product, at_date, aml_vals_list)
        if vals_list:
            aml_vals_list += vals_list
        vals_list = self._get_continental_realtime_variation_vals(accounts_by_product, at_date, aml_vals_list)
        if vals_list:
            aml_vals_list += vals_list
        return aml_vals_list

    def _get_partial_stock_variation_vals(self, products, accounts_by_product, at_date=None, extra_aml_vals_list=None):
        """Stock Variation vals of a PARTIAL closing (product filter), attributed per
        product.

        Not delegated to ``_get_stock_valuation_account_vals``: the standard reads the
        booked value with ``stock_accounting_value``, the WHOLE balance of the valuation
        account, so a closing filtered by product took in the value already booked for the
        other products sharing that account and the entry came out with the wrong amount
        —and often the wrong sign— against a report that does scope it (task 64440).

        Built from the same balance the report shows, so the entry books exactly the
        variation on screen.
        """
        report = self.env["stock_account.stock.valuation.report"]
        inventory_data = self.stock_value(accounts_by_product, at_date)
        accounting_data = report._get_report_accounting_data(
            self, accounts_by_product, products, at_date, product_scope=True
        )
        balances_by_account = report._get_total_variation_balance(
            self, at_date, inventory_data, accounting_data, extra_aml_vals_list=extra_aml_vals_list
        )
        vals_list = report._get_variation_aml_vals(self, balances_by_account)
        return self._split_valuation_vals_by_product(vals_list, accounts_by_product, at_date)

    def _get_line_type_closing_vals(self, at_date=None):
        """Vals of a closing limited to one ORIGIN of the variation (Movement Type
        filter).

        Reuses the very breakdown the report shows, so the entry books exactly the
        amount on screen. Both origins are complementary and add up to the whole
        variation, so closing one and then the other equals the full closing.

        Location reclassifications and the continental perpetual variation are not
        added here: they belong to neither origin, and the full closing books them.
        """
        self.ensure_one()
        line_types = self.env.context.get(CLOSING_LINE_TYPES_CTX)
        report = self.env["stock_account.stock.valuation.report"]
        if isinstance(at_date, str):
            at_date = fields.Date.from_string(at_date)
        if at_date == fields.Date.context_today(self):
            at_date = False
        closing_product_ids = self.env.context.get(CLOSING_PRODUCT_CTX)
        if closing_product_ids is not None:
            products = self.env["product.product"].browse(closing_product_ids)
        else:
            products = report._get_filtered_valued_products(self, at_date, None, None, None, None)
        if not products:
            return []
        accounts_by_product = self._get_accounts_by_product(products=products)
        inventory_data = self.stock_value(accounts_by_product, at_date)
        # Combined with a product filter, the booked value is the one attributable to those
        # products, as in the report: the Product Value component is a REMAINDER over this
        # balance, so the whole account balance would attribute to the filtered products
        # what was already booked for the others.
        accounting_data = report._get_report_accounting_data(
            self, accounts_by_product, products, at_date, product_scope=closing_product_ids is not None
        )
        vals_list = report._get_valuation_report_variation_components(
            self, products, accounts_by_product, at_date, line_types, inventory_data, accounting_data
        )
        # The per-origin entry is attributed per product too, but with the contribution
        # of THAT origin: splitting the whole pending difference here would
        # over-attribute it, as this entry books only a portion.
        deltas_by_product = report._get_line_type_deltas_by_product(
            self, products, accounts_by_product, at_date, line_types
        )
        return self._split_valuation_vals_by_product(
            vals_list, accounts_by_product, at_date, deltas_by_product=deltas_by_product
        )

    def _get_location_valuation_vals(self, at_date=None, location_domain=False):
        """Partial closing: scope the location reclassifications to the ``stock.move``
        records of the filtered products. Without the context key, delegate to the
        standard.

        MAINTENANCE NOTE: the body is a copy of
        ``stock_account/models/res_company.py::_get_location_valuation_vals`` (v19.0)
        with a single change, the move domains add
        ``('product_id', 'in', closing_product_ids)``. Re-sync on Odoo upgrades.
        """
        closing_product_ids = self.env.context.get(CLOSING_PRODUCT_CTX)
        if closing_product_ids is None:
            return super()._get_location_valuation_vals(at_date=at_date, location_domain=location_domain)

        location_domain = Domain.AND(
            [
                location_domain or [],
                [("valuation_account_id", "!=", False)],
                [("company_id", "=", self.id)],
            ]
        )
        amls_vals_list = []
        valued_location = self.env["stock.location"].search(location_domain)
        last_closing_date = self._get_last_closing_date()
        moves_base_domain = Domain(
            [
                ("product_id.is_storable", "=", True),
                ("product_id.valuation", "=", "periodic"),
                ("product_id", "in", closing_product_ids),
            ]
        )
        if last_closing_date:
            moves_base_domain &= Domain([("date", ">", last_closing_date)])
        if at_date:
            moves_base_domain &= Domain([("date", "<=", at_date)])
        moves_in_domain = (
            Domain(
                [
                    ("is_out", "=", True),
                    ("company_id", "=", self.id),
                    ("location_dest_id", "in", valued_location.ids),
                ]
            )
            & moves_base_domain
        )
        moves_in_by_location = self.env["stock.move"]._read_group(
            moves_in_domain,
            ["location_dest_id", "product_category_id"],
            ["value:sum"],
        )
        moves_out_domain = (
            Domain(
                [
                    ("is_in", "=", True),
                    ("company_id", "=", self.id),
                    ("location_id", "in", valued_location.ids),
                ]
            )
            & moves_base_domain
        )
        moves_out_by_location = self.env["stock.move"]._read_group(
            moves_out_domain,
            ["location_id", "product_category_id"],
            ["value:sum"],
        )
        account_balance = defaultdict(float)
        for location, category, value in moves_in_by_location:
            stock_valuation_acc = category.property_stock_valuation_account_id or self.account_stock_valuation_id
            account_balance[location.valuation_account_id, stock_valuation_acc] += value
        for location, category, value in moves_out_by_location:
            stock_valuation_acc = category.property_stock_valuation_account_id or self.account_stock_valuation_id
            account_balance[location.valuation_account_id, stock_valuation_acc] -= value
        for (location_account, stock_account), balance in account_balance.items():
            if balance == 0:
                continue
            amls_vals = self._prepare_inventory_aml_vals(
                location_account,
                stock_account,
                balance,
                self.env._("Closing: Location Reclassification - [%(account)s]", account=location_account.display_name),
            )
            amls_vals_list += amls_vals
        return amls_vals_list
