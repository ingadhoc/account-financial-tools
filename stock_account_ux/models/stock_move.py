from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError


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

    def _related_account_move_depends(self):
        """Dependencies of ``related_account_move_id``. The related invoices are reached
        the way ``_get_related_invoices`` reaches them in ``sale_stock`` and
        ``purchase_stock`` —the sale order of the picking, the purchase order of the
        move's line— only when those modules are installed."""
        depends = [
            "account_move_id",
            "account_move_id.state",
            "picking_id",
            "state",
            "product_id.valuation",
            "product_value_ids.account_move_id",
            "product_value_ids.account_move_id.state",
            "product_value_ids.date",
        ]
        if "sale_id" in self.env["stock.picking"]._fields:
            depends.append("picking_id.sale_id.order_line.invoice_lines.move_id.state")
        if "purchase_line_id" in self._fields:
            depends.append("purchase_line_id.order_id.order_line.invoice_lines.move_id.state")
        return depends

    @api.depends(lambda self: self._related_account_move_depends())
    def _compute_related_account_move_id(self):
        # The value adjustment entry wins, as it is the one reflecting the move's CURRENT
        # valuation. The original entry stays in the standard ``account_move_id``.
        revaluation_entry_by_move = self._get_booked_revaluation_entries()
        # The related invoice only reflects the valuation of THIS move when the product is
        # valued perpetually, i.e. on invoicing. Under periodic valuation the cost is not
        # booked in the invoice but in the global closing entry, so the invoice must not
        # be shown as the related entry until that closing exists.
        perpetual_moves = self.filtered(lambda move: move.product_id.valuation == "real_time")
        invoices_by_picking = perpetual_moves._get_related_invoices_by_picking()
        for move in self:
            revaluation_entry = revaluation_entry_by_move.get(move.id)
            if revaluation_entry:
                move.related_account_move_id = revaluation_entry
                continue
            # The move's own valuation entry (perpetual) or the closing entry it belongs
            # to (periodic), both in ``account_move_id``. Unposted ones are left out.
            entries = move.account_move_id.filtered(lambda entry: entry.state == "posted")
            if move in perpetual_moves:
                entries |= invoices_by_picking.get(move.picking_id.id, self.env["account.move"])
            # The field is a Many2one, so the first available entry wins. The union keeps
            # the order, hence the valuation entry (``account_move_id``) first and the
            # related invoice as a fallback.
            move.related_account_move_id = entries[:1]

    def _get_related_invoices_by_picking(self):
        """Posted related invoices of these moves, per picking: ``{picking id: invoices}``.

        The batch version of ``_get_related_invoices`` (``sale_stock`` and
        ``purchase_stock``), which resolves them one move at a time with a search each.
        Both overrides read them off the picking —the customer invoices through its sale
        order, the vendor bills through the purchase orders it receives for—, so they are
        resolved once per picking here. Keep it aligned with those overrides.
        """
        invoices_by_picking = defaultdict(lambda: self.env["account.move"])
        pickings = self.picking_id
        if not pickings:
            return invoices_by_picking
        if "sale_id" in pickings._fields:
            for picking in pickings:
                invoices = picking.sale_id.invoice_ids.filtered(lambda entry: entry.state == "posted")
                if invoices:
                    invoices_by_picking[picking.id] |= invoices
        PurchaseOrder = self.env.get("purchase.order")
        if PurchaseOrder is not None and "picking_ids" in PurchaseOrder._fields:
            picking_ids = set(pickings.ids)
            for order in PurchaseOrder.search([("picking_ids", "in", pickings.ids)]):
                bills = order.invoice_ids.filtered(lambda entry: entry.state == "posted")
                if not bills:
                    continue
                for picking_id in set(order.picking_ids.ids) & picking_ids:
                    invoices_by_picking[picking_id] |= bills
        return invoices_by_picking

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

        A ``value`` differing from quantity × standard cost means there was a manual
        adjustment, and then a ``product.value`` points at the move: that move is left out
        of the Stock Moves component (see ``_get_line_type_move_domain``) and its value is
        contributed by the value adjustments component, which is where it belongs.

        Single home of this criterion, shared by the report's breakdown of the variation
        (Movement Type filter) and by the manual valuation of moves, so both measure the
        same thing.
        """
        self.ensure_one()
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
