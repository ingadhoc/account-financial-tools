from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL, split_every


class StockMove(models.Model):
    _inherit = "stock.move"

    # ``account_move_id`` (stored) already exists in stock_account: it holds the
    # perpetual valuation entry and, through the res.company override, the periodic
    # closing one. It is left untouched. This navigable field points at the entry
    # reflecting the move's CURRENT valuation —the booked value adjustment if there is
    # one, the original otherwise— to reach it in one click from the moves report.
    # Only POSTED entries count: a closing sent back to draft or cancelled booked
    # nothing, so showing it here would say the move is valued when it is not
    # (functional feedback, task 64440). The stored ``account_move_id`` keeps the
    # reference either way, so re-posting the entry brings the link back.
    # Stored: the valuation report and the closing filter every move of the company by
    # it, and answering "is there an entry" on the fly materialised the posted entries
    # and the invoiced pickings of the whole base on each call (task 75652). The
    # dependencies below keep it up to date, related invoices included.
    related_account_move_id = fields.Many2one(
        comodel_name="account.move",
        compute="_compute_related_account_move_id",
        store=True,
        index="btree_not_null",
        string="Journal Entry",
    )
    # Moves whose valuation was already booked in v18 (the 18->19 post-migration
    # re-attached the entry to ``account_move_id``). The expense was recognised in the
    # previous version, so invoicing them in v19 must not generate the anglo-saxon COGS
    # again. See the ``_stock_account_prepare_realtime_out_lines_vals`` override in
    # account_move.py.
    stock_valuation_migrated = fields.Boolean(
        string="Valuation Booked in v18",
        default=False,
        copy=False,
    )
    # A move's value adjustments are stored as ``product.value`` records, and they are
    # booked in the closing entry, not in the move's original entry. This inverse
    # relation is what lets ``related_account_move_id`` reach that entry.
    product_value_ids = fields.One2many(
        comodel_name="product.value",
        inverse_name="move_id",
        string="Value Adjustments",
        readonly=True,
    )

    # Every posted entry tied to the move, while ``related_account_move_id`` keeps only
    # the one reflecting its current valuation: its own entry, its value adjustments and
    # the invoices or credit notes of its line that fall on its quantity (a move invoiced
    # in two parts, an invoice cancelled and made again). Computed on read: it only feeds
    # the list button, so it is never searched or grouped by.
    all_account_move_ids = fields.Many2many(
        comodel_name="account.move",
        compute="_compute_all_account_move_ids",
        string="All Journal Entries",
    )
    account_move_count = fields.Integer(
        compute="_compute_all_account_move_ids",
        string="Journal Entries Count",
    )

    def _related_account_move_depends(self):
        """Dependencies of ``related_account_move_id``. The related invoices are reached
        the way ``_get_related_invoice_by_move`` reaches them, through the move's own sale
        or purchase line, only when those modules are installed. The other moves of the
        line and its delivered quantity count too, as they decide which quantity of the
        line each move stands for."""
        depends = [
            "account_move_id",
            "account_move_id.state",
            "account_move_id.reversal_move_ids.state",
            "account_move_id.reversal_move_ids.reversal_move_ids.state",
            "state",
            "product_id.valuation",
            "product_value_ids.account_move_id",
            "product_value_ids.account_move_id.state",
            "product_value_ids.date",
        ]
        for spec in self._order_line_specs():
            field = spec["field"]
            depends += [
                f"{field}.invoice_lines.move_id.state",
                f"{field}.move_ids.state",
                f"{field}.{spec['delivered_field']}",
            ]
        return depends

    @api.depends(lambda self: self._related_account_move_depends())
    def _compute_related_account_move_id(self):
        # A closing links, and later posts, every unaccounted move of the company at once:
        # fetch only what is read here, or the whole move gets prefetched for each of them.
        self.fetch(["account_move_id", "product_id"])
        # The value adjustment entry wins, as it is the one reflecting the move's CURRENT
        # valuation. The original entry stays in the standard ``account_move_id``.
        revaluation_entry_by_move = self._get_booked_revaluation_entries()
        # The move's own valuation entry (perpetual) or the closing entry it belongs to
        # (periodic), both in ``account_move_id``. Unposted ones are left out.
        posted_entries = self.account_move_id.filtered(lambda entry: entry.state == "posted")
        # A perpetual move booked by a closing whose invoice reversed that part of it: the
        # invoice books it now, and with no invoice (cancelled by a credit note) it is
        # pending again, so that a new closing or another invoice books it.
        reversal_by_move = (
            self.filtered(lambda move: move.account_move_id in posted_entries)
            ._filter_real_time_valuation()
            ._get_closing_reversal_by_move()
        )
        # The related invoice only reflects the valuation of THIS move when the product is
        # valued perpetually, i.e. on invoicing. Under periodic valuation the cost is not
        # booked in the invoice but in the global closing entry, so the invoice must not
        # be shown as the related entry until that closing exists. It is only a fallback,
        # so it is resolved just for the moves with no entry of their own.
        invoice_moves = self.filtered(
            lambda move: move.id not in revaluation_entry_by_move
            and (move.account_move_id not in posted_entries or move.id in reversal_by_move)
        )._filter_real_time_valuation()
        invoice_by_move = invoice_moves._get_related_invoice_by_move()
        for move in self:
            if move.id in revaluation_entry_by_move:
                move.related_account_move_id = revaluation_entry_by_move[move.id]
            elif move.id in reversal_by_move:
                fully_reversed = reversal_by_move[move.id][1]
                fallback = False if fully_reversed else move.account_move_id
                move.related_account_move_id = invoice_by_move.get(move.id, fallback)
            elif move.account_move_id in posted_entries:
                move.related_account_move_id = move.account_move_id
            elif move in invoice_moves:
                move.related_account_move_id = invoice_by_move.get(move.id, False)
            else:
                move.related_account_move_id = False

    @api.depends("related_account_move_id")
    def _compute_all_account_move_ids(self):
        # sudo: same reason as ``_get_booked_revaluation_entries``, the column is shown in
        # lists that people without access to value adjustments or invoices also open.
        sudo_moves = self.sudo()
        # Invoices value the move only under perpetual valuation, as in the stored compute.
        real_time_moves = sudo_moves._filter_real_time_valuation()
        invoices_by_move = real_time_moves._get_related_invoices_by_move()
        reversal_by_move = real_time_moves._get_closing_reversal_by_move()
        Entry = self.env["account.move"].sudo()
        for move, sudo_move in zip(self, sudo_moves, strict=True):
            entries = sudo_move.related_account_move_id | sudo_move.account_move_id
            entries |= sudo_move.product_value_ids.account_move_id
            entries |= Entry.browse(invoices_by_move.get(move.id, (False, ()))[1])
            entries |= reversal_by_move.get(move.id, (Entry, False))[0]
            entries = entries.filtered(lambda entry: entry.state == "posted")
            move.all_account_move_ids = entries.sorted(lambda entry: (entry.date, entry.id))
            move.account_move_count = len(entries)

    def action_view_account_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Journal Entries of %s", self._get_valuation_labels()[0]),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(self.env.ref("account.view_move_tree").id, "list"), (False, "form")],
            "domain": [("id", "in", self.all_account_move_ids.ids)],
            "context": {"create": False, "edit": False},
            "target": "new",
        }

    def _recompute_related_account_move(self, batch_size=1000):
        """Recompute ``related_account_move_id`` in batches, flushing and freeing the cache
        after each one, so a big set of moves stays within memory."""
        field = self._fields["related_account_move_id"]
        self.env.flush_all()
        for ids in split_every(batch_size, self.ids):
            batch = self.browse(ids)
            self.env.add_to_compute(field, batch)
            batch._recompute_recordset(["related_account_move_id"])
            self.env.flush_all()
            self.env.invalidate_all()

    def _filter_real_time_valuation(self):
        """Moves whose product is valued perpetually in the move's company.

        The product's ``valuation`` depends on the company in the context, and the stored
        compute runs in the company of whoever triggers it: read as is, a move of a
        perpetual company triggered from a periodic one got the periodic answer, and the
        other way round."""
        return self.browse().union(
            *(
                moves.with_company(company).filtered(lambda move: move.product_id.valuation == "real_time")
                for company, moves in self.grouped("company_id").items()
            )
        )

    def _order_line_specs(self):
        """How each kind of order line reaches its moves and invoices, for the installed
        modules. A move goes forward when it leaves towards the partner (a delivery) or
        comes from it (a receipt), and backward when it is the return."""
        specs = []
        if "sale_line_id" in self._fields:
            specs.append(
                {
                    "field": "sale_line_id",
                    "line_table": "sale_order_line",
                    "delivered_field": "qty_delivered",
                    "partner_usage": "customer",
                    "forward_location": "location_dest_id",
                    "backward_location": "location_id",
                    "refund_type": "out_refund",
                    "entries": lambda line_ids: SQL(
                        """
                        SELECT rel.order_line_id AS line_id, aml.quantity, aml.product_uom_id,
                               entry.id, entry.date, entry.move_type
                          FROM sale_order_line_invoice_rel rel
                          JOIN account_move_line aml ON aml.id = rel.invoice_line_id
                          JOIN account_move entry ON entry.id = aml.move_id
                         WHERE rel.order_line_id = ANY(%(line_ids)s)
                           AND entry.state = 'posted'
                           AND entry.move_type IN ('out_invoice', 'out_refund')
                        """,
                        line_ids=line_ids,
                    ),
                }
            )
        if "purchase_line_id" in self._fields:
            specs.append(
                {
                    "field": "purchase_line_id",
                    "line_table": "purchase_order_line",
                    "delivered_field": "qty_received",
                    "partner_usage": "supplier",
                    "forward_location": "location_id",
                    "backward_location": "location_dest_id",
                    "refund_type": "in_refund",
                    "entries": lambda line_ids: SQL(
                        """
                        SELECT aml.purchase_line_id AS line_id, aml.quantity, aml.product_uom_id,
                               entry.id, entry.date, entry.move_type
                          FROM account_move_line aml
                          JOIN account_move entry ON entry.id = aml.move_id
                         WHERE aml.purchase_line_id = ANY(%(line_ids)s)
                           AND entry.state = 'posted'
                           AND entry.move_type IN ('in_invoice', 'in_refund')
                        """,
                        line_ids=line_ids,
                    ),
                }
            )
        return specs

    def _get_related_invoice_by_move(self):
        """Posted invoice that covers each of these moves: ``{move id: invoice id}``. See
        ``_get_related_invoices_by_move``."""
        return {
            move_id: covering_id
            for move_id, (covering_id, _entry_ids) in self._get_related_invoices_by_move().items()
            if covering_id
        }

    def _get_related_invoices_by_move(self):
        """``{move id: (covering invoice id or False, ids of the invoices on its quantity)}``.

        Read off the move's own order line —the customer invoices of its sale line, the
        vendor bills of its purchase line—, not off the picking as ``_get_related_invoices``
        (``sale_stock`` and ``purchase_stock``) does: through the picking, a move took the
        invoice of another line of the same order, such as a down payment invoice.

        And matched by quantity: the done moves of the line add up in date order (returns
        subtract), and each move stands for its stretch of the line, from what was
        delivered before it to what was delivered up to it, less what later returns took
        back. Its invoice is the one that brought the net invoiced quantity (credit notes
        subtract) to where it ends up in that stretch. A later partial delivery is not
        booked by the invoice of an earlier one, and an invoice cancelled by a credit note
        does not book anything: when nothing of the stretch is invoiced, net of credit
        notes, the move has no related invoice. A move invoiced in part takes the invoice
        that bills that part.

        Kit components are not in the unit of the line, so they stand for the delivered
        quantity of the whole line, as computed by Odoo (``qty_delivered`` /
        ``qty_received``). A move that neither leaves to nor comes from the partner (a
        pick of a multi-step delivery) is not valued and has no related invoice. When a
        move is on both a sale and a purchase line (dropship), the most recent invoice
        wins. Resolved in SQL for the whole batch."""
        if not self.ids:
            return {}
        specs = self._order_line_specs()
        # Read in SQL: what the ORM still holds in cache (a move just done, an invoice just
        # posted, the very changes that trigger this compute) has to reach the database.
        self.env["stock.location"].flush_model(["usage"])
        self.env["account.move"].flush_model(["state", "date", "move_type"])
        self.env["account.move.line"].flush_model(["move_id", "quantity", "product_uom_id"])
        move_fields = ["state", "date", "product_id", "quantity", "product_uom", "location_id", "location_dest_id"]
        for spec in specs:
            move_fields.append(spec["field"])
            OrderLine = self.env[self._fields[spec["field"]].comodel_name]
            line_fields = ["product_id", "product_uom_id", spec["delivered_field"]]
            if OrderLine._fields["invoice_lines"].type == "many2many":
                line_fields.append("invoice_lines")
            OrderLine.flush_model(line_fields)
        if "purchase_line_id" in self.env["account.move.line"]._fields:
            self.env["account.move.line"].flush_model(["purchase_line_id"])
        self.env["stock.move"].flush_model(move_fields)
        best, entry_ids = {}, {}
        for spec in specs:
            for move_id, (covering, contributing) in self._get_covering_entries(spec).items():
                if covering and (move_id not in best or covering["key"] > best[move_id]["key"]):
                    best[move_id] = covering
                entry_ids.setdefault(move_id, set()).update(contributing)
        return {
            move_id: (best[move_id]["id"] if move_id in best else False, entry_ids[move_id]) for move_id in entry_ids
        }

    def _get_covering_entries(self, spec):
        """``{move id: (covering, contributing)}`` for the moves of ``self`` on one kind
        of order line: the covering invoice (``id`` and its sort ``key``, or None) and the
        ids of every invoice or credit note that falls on the move's quantity."""
        field = spec["field"]
        line_ids = list(
            {
                line_id
                for (line_id,) in self.env.execute_query(
                    SQL(
                        "SELECT %s FROM stock_move WHERE id = ANY(%s) AND %s IS NOT NULL",
                        SQL.identifier(field),
                        self.ids,
                        SQL.identifier(field),
                    )
                )
            }
        )
        if not line_ids:
            return {}
        lines = {
            line_id: {"product_id": product_id, "uom_id": uom_id, "delivered": delivered or 0.0}
            for line_id, product_id, uom_id, delivered in self.env.execute_query(
                SQL(
                    "SELECT id, product_id, product_uom_id, %s FROM %s WHERE id = ANY(%s)",
                    SQL.identifier(spec["delivered_field"]),
                    SQL.identifier(spec["line_table"]),
                    line_ids,
                )
            )
        }
        moves_by_line = {}
        for move_id, line_id, product_id, quantity, uom_id, direction in self.env.execute_query(
            SQL(
                """
                SELECT move.id, move.%(field)s, move.product_id, move.quantity, move.product_uom,
                       CASE WHEN forward_location.usage = %(usage)s THEN 1
                            WHEN backward_location.usage = %(usage)s THEN -1
                            ELSE 0 END
                  FROM stock_move move
                  JOIN stock_location forward_location ON forward_location.id = move.%(forward)s
                  JOIN stock_location backward_location ON backward_location.id = move.%(backward)s
                 WHERE move.%(field)s = ANY(%(line_ids)s)
                   AND move.state = 'done'
                 ORDER BY move.date, move.id
                """,
                field=SQL.identifier(field),
                forward=SQL.identifier(spec["forward_location"]),
                backward=SQL.identifier(spec["backward_location"]),
                usage=spec["partner_usage"],
                line_ids=line_ids,
            )
        ):
            moves_by_line.setdefault(line_id, []).append((move_id, product_id, quantity, uom_id, direction))
        entries_by_line = {}
        for line_id, quantity, uom_id, entry_id, date, move_type in self.env.execute_query(
            SQL(
                "SELECT * FROM (%s) entries ORDER BY entries.date, entries.id",
                spec["entries"](line_ids),
            )
        ):
            sign = -1 if move_type == spec["refund_type"] else 1
            entries_by_line.setdefault(line_id, []).append(
                {"id": entry_id, "key": (date, entry_id), "quantity": sign * quantity, "uom_id": uom_id}
            )
        Uom = self.env["uom.uom"]
        requested = set(self.ids)
        result = {}
        for line_id, line_moves in moves_by_line.items():
            line = lines[line_id]
            line_uom = Uom.browse(line["uom_id"])
            entries = entries_by_line.get(line_id, [])
            invoiced = []
            for entry in entries:
                quantity = entry["quantity"]
                if entry["uom_id"] and entry["uom_id"] != line_uom.id:
                    quantity = Uom.browse(entry["uom_id"])._compute_quantity(quantity, line_uom, round=False)
                invoiced.append((entry, quantity))
            own_moves = [row for row in line_moves if row[1] == line["product_id"] and row[4]]
            stretches = self._get_quantity_stretches(
                [
                    direction * Uom.browse(uom_id)._compute_quantity(quantity, line_uom, round=False)
                    for _move_id, _product_id, quantity, uom_id, direction in own_moves
                ]
            )
            lower_by_move = {row[0]: stretch[0] for row, stretch in zip(own_moves, stretches, strict=True)}
            required_by_move = {row[0]: stretch[1] for row, stretch in zip(own_moves, stretches, strict=True)}
            for move_id, _product_id, _quantity, _uom_id, direction in line_moves:
                if move_id not in requested or not direction:
                    continue
                if move_id in required_by_move:
                    lower, required = lower_by_move[move_id], required_by_move[move_id]
                else:
                    lower, required = 0.0, line["delivered"]
                result[move_id] = (
                    self._get_covering_entry(invoiced, lower, required, line_uom),
                    self._get_contributing_entries(invoiced, lower, required, line_uom),
                )
        return result

    @api.model
    def _get_quantity_stretches(self, quantities):
        """``[(lower, upper)]``: the stretch of the line each move stands for, given the
        signed quantities of the line's own moves in date order (returns subtract). It
        runs from where the previous move ended to the running quantity, capped by what
        later returns leave of it."""
        running, cumulative = 0.0, []
        for quantity in quantities:
            running += quantity
            cumulative.append(running)
        for index in range(len(cumulative) - 2, -1, -1):
            cumulative[index] = min(cumulative[index], cumulative[index + 1])
        return [(cumulative[index - 1] if index else 0.0, upper) for index, upper in enumerate(cumulative)]

    @api.model
    def _get_order_line_stretches(self, order_line):
        """``{stock.move: (lower, upper)}`` of the done moves that deliver (or receive) the
        order line's own product, in the unit of the line. Returns are left out: they
        only cap the stretches of the moves they take back."""
        spec = next(
            (spec for spec in self._order_line_specs() if self._fields[spec["field"]].comodel_name == order_line._name),
            None,
        )
        if not spec:
            return {}
        line_uom = order_line.product_uom_id
        rows = []
        moves = order_line.move_ids.filtered(
            lambda move: move.state == "done" and move.product_id == order_line.product_id
        ).sorted(lambda move: (move.date, move.id))
        for move in moves:
            if move[spec["forward_location"]].usage == spec["partner_usage"]:
                direction = 1
            elif move[spec["backward_location"]].usage == spec["partner_usage"]:
                direction = -1
            else:
                continue
            rows.append((move, direction * move.product_uom._compute_quantity(move.quantity, line_uom, round=False)))
        stretches = self._get_quantity_stretches([quantity for _move, quantity in rows])
        return {move: stretch for (move, quantity), stretch in zip(rows, stretches, strict=True) if quantity > 0}

    @api.model
    def _get_closing_stretches(self, order_line):
        """``{closing: [(move, lower, upper)]}``: the stretches of the order line that a
        posted closing entry booked. Moves valued in v18 have no closing of their own."""
        by_closing = {}
        for move, (lower, upper) in self._get_order_line_stretches(order_line).items():
            closing = move.account_move_id
            if closing.state != "posted" or closing.move_type != "entry" or move.stock_valuation_migrated:
                continue
            if order_line.product_uom_id.compare(upper, lower) <= 0:
                continue
            by_closing.setdefault(closing, []).append((move, lower, upper))
        return by_closing

    def _get_closing_reversal_by_move(self):
        """``{move id: (reversals, fully reversed)}`` for the moves whose closing entry was
        reversed, in part, by the invoices of their order line.

        A closing books the moves of a line in order, and its reversals take that booked
        quantity back in the same order: a move is fully reversed when its whole stretch
        falls within what the reversals of its closing add up to."""
        result = {}
        closings = self.account_move_id.filtered(
            lambda entry: entry.state == "posted" and entry.move_type == "entry" and entry.reversal_move_ids
        )
        if not closings:
            return result
        AccountMoveLine = self.env["account.move.line"]
        # A closing links every move of the period, and each reversal recomputes them all:
        # read the reversal lines once, and go on only with the order lines they bill.
        reversal_lines = (
            AccountMoveLine.sudo()
            .search(
                [
                    ("move_id.reversed_entry_id", "in", closings.ids),
                    ("parent_state", "=", "posted"),
                    ("cogs_origin_id", "!=", False),
                ]
            )
            .filtered(lambda line: not line.move_id.reversal_move_ids.filtered(lambda entry: entry.state == "posted"))
        )
        lines_by_key = {}
        for line in reversal_lines:
            order_line = line.cogs_origin_id._get_stock_order_line()
            if order_line:
                key = (line.move_id.reversed_entry_id, order_line)
                lines_by_key[key] = lines_by_key.get(key, AccountMoveLine) | line
        if not lines_by_key:
            return result
        stretches_cache = {}
        for move in self.filtered(lambda move: move.account_move_id in closings):
            order_line = AccountMoveLine._get_stock_order_line_of_move(move)
            closing = move.account_move_id
            lines = lines_by_key.get((closing, order_line))
            if not lines:
                continue
            if order_line not in stretches_cache:
                stretches_cache[order_line] = self._get_closing_stretches(order_line)
            reversed_quantity = sum(lines.mapped("quantity"))
            booked = 0.0
            fully_reversed = False
            for stretch_move, lower, upper in stretches_cache[order_line].get(closing, []):
                booked += upper - lower
                if stretch_move == move:
                    fully_reversed = order_line.product_uom_id.compare(booked, reversed_quantity) <= 0
                    break
            result[move.id] = (lines.move_id, fully_reversed)
        return result

    @api.model
    def _get_covering_entry(self, invoiced, lower, upper, uom):
        """The entry that brought the running net invoiced quantity, for good, to where it
        ends up inside the move's stretch of the line ``(lower, upper]``: up to ``upper``
        when the line covers the whole move, or up to the line's net total when it covers
        part of it (the invoice still standing when another one was cancelled by a credit
        note). None when nothing of the stretch is invoiced, net of credit notes: a
        delivery not invoiced yet, or an invoice cancelled and not made again.

        ``invoiced`` is the list of ``(entry, signed quantity)`` by date, then creation (a
        credit note and the invoice made again the same day keep their real order, which
        their names do not). A move standing for no quantity (all of it returned, a kit
        not delivered yet) takes the most recent entry, as long as the line is still
        invoiced."""
        if not invoiced:
            return None
        total = sum(quantity for _entry, quantity in invoiced)
        if uom.compare(upper, lower) <= 0:
            return invoiced[-1][0] if uom.compare(total, 0.0) > 0 else None
        target = min(total, upper)
        if uom.compare(target, lower) <= 0:
            return None
        covering, running = None, 0.0
        for entry, quantity in invoiced:
            previous, running = running, running + quantity
            if uom.compare(previous, target) < 0 <= uom.compare(running, target):
                covering = entry
        return covering

    @api.model
    def _get_contributing_entries(self, invoiced, lower, upper, uom):
        """Ids of the entries whose quantity falls on the move's stretch of the line,
        ``(lower, upper]``: the invoices that bill part of it and the credit notes that
        take part of it back. A move standing for no quantity (all of it returned, a kit
        not delivered yet) gets every entry of the line."""
        if uom.compare(upper, lower) <= 0:
            return {entry["id"] for entry, _quantity in invoiced}
        ids, running = set(), 0.0
        for entry, quantity in invoiced:
            previous, running = running, running + quantity
            if uom.compare(max(min(previous, running), lower), min(max(previous, running), upper)) < 0:
                ids.add(entry["id"])
        return ids

    def _get_booked_revaluation_entries(self):
        """Last entry that booked a value adjustment, per move.

        Read in ``sudo()``: the entry column shows up in the moves lists Accounting uses,
        and ``product.value`` is access-restricted out of the box, so the computation
        cannot depend on the permissions of whoever is looking at the list. The read ACL
        the module adds is for the filtering, which does run as the user.
        """
        if not self.ids:
            return {}
        product_values = (
            self.env["product.value"]
            .sudo()
            .search(
                [
                    ("move_id", "in", self.ids),
                    ("account_move_id", "!=", False),
                    ("account_move_id.state", "=", "posted"),
                ],
                order="date asc, id asc",
            )
        )
        # Ascending order: per move the last write wins, i.e. the most recent booked
        # adjustment.
        return {product_value.move_id.id: product_value.account_move_id.id for product_value in product_values}

    def _get_inventory_value(self):
        """What the move contributes to the inventory VALUATION: its ``value``.

        This holds for the three costing methods, standard cost included: a normal receipt
        of a standard cost product is already valued at the standard cost and not at what
        was paid (checked on v19: 10 units at 5 with a standard of 10 leaves ``value`` =
        100, not 50, and the price difference goes to its own account). There is no need
        to rebuild the cost in force at the move's date.

        A manual adjustment (a ``product.value`` pointing at the move) is part of that
        value under AVCO/FIFO, where it does move the product valuation. Under standard
        cost it does not: the inventory stays at quantity × standard cost, so the move
        contributes what it was worth before its first adjustment.

        Single home of this criterion, shared by the report's breakdown of the variation
        (Movement Type filter) and by the manual valuation of moves, so both measure the
        same thing.
        """
        self.ensure_one()
        if self.product_id.with_company(self.company_id).cost_method == "standard":
            first_adjustment = self.sudo().product_value_ids.sorted(lambda pv: (pv.date, pv.id))[:1]
            if first_adjustment:
                return first_adjustment.previous_value
        return self.value

    def _get_valuation_labels(self):
        """Labels to name moves in user messages. ``reference`` is empty on moves with no
        picking (created by hand or by internal processes), so it cannot be used directly
        in a ``join``."""
        return [move.reference or move.display_name or f"#{move.id}" for move in self]

    def action_value_moves(self):
        """Open the wizard that builds the draft valuation entry of the selected moves."""
        moves = self.filtered(lambda m: m.state == "done")
        if not moves:
            raise UserError(self.env._("Only done moves can be valued."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Value Stock Moves"),
            "res_model": "stock.move.valuation",
            "view_mode": "form",
            "target": "new",
            "context": {**self.env.context, "default_move_ids": moves.ids},
        }

    def _set_value(self, correction_quantity=None):
        """Do not revalue on invoicing the moves already valued in v18.

        Out of the box ``account.move._post`` calls ``_set_value`` on the invoice's
        incoming/dropship moves to recompute their ``value`` —and from it the product's
        ``standard_price``— out of the invoiced price. For a migrated move that value
        already comes from v18 (the post-migration backfilled it), so recomputing it would
        overwrite it on a different basis. Only skipped in the invoice posting flow, which
        sets the ``skip_migrated_stock_revaluation`` context; every other call to
        ``_set_value`` is left untouched. See task 70174.
        """
        moves = self
        if self.env.context.get("skip_migrated_stock_revaluation"):
            moves = self.filtered(lambda m: not (m.stock_valuation_migrated and (m.is_in or m.is_dropship)))
        return super(StockMove, moves)._set_value(correction_quantity=correction_quantity)

    def _get_migrated_valuation_counterpart_account(self):
        """Counterpart account of the valuation entry v18 left attached to
        ``account_move_id`` (18->19 post-migration).

        In that entry the receipt was booked as an asset increase: debit to the stock
        valuation account against this counterpart, typically a goods purchase account.
        That is the account the v19 invoice line has to be booked to, so stock valuation is
        not debited twice. Returns an empty recordset when there is no entry or the
        counterpart cannot be determined.
        """
        self.ensure_one()
        entry = self.account_move_id
        if not entry:
            return self.env["account.account"]
        accounts = self.product_id.product_tmpl_id.with_company(self.company_id).get_product_accounts()
        valuation_account = accounts.get("stock_valuation")
        counterpart = entry.line_ids.filtered(lambda line: line.account_id and line.account_id != valuation_account)
        return counterpart[:1].account_id
