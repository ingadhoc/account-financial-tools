from odoo import api, fields, models


class ProductValue(models.Model):
    _inherit = "product.value"

    # Out of the box ``product.value`` keeps no reference to the entry that booked the
    # adjustment: a cost change enters the closing entry aggregated per account and the
    # adjustment is left orphaned, with no way to tell whether it was booked, or where.
    # With this field the valuation closing (see
    # ``res.company.action_close_stock_valuation``) marks the adjustments it books, and
    # "no entry" identifies exactly the ones still making up the difference to adjust.
    account_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="Inventory valuation closing entry that booked this value adjustment. Empty "
        "means the adjustment is not booked yet: it is part of the difference to adjust "
        "shown by the valuation report's variation.",
    )
    previous_value = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
        copy=False,
        help="Value in force right before this adjustment. Captured when it is recorded, "
        "because afterwards it can no longer be rebuilt.",
    )
    delta = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_delta",
        help="Variation this adjustment introduced, in the SAME unit as the Value field: "
        "the move total value when the adjustment is on a move, the unit price when it is "
        "a product or lot price change.",
    )

    @api.depends("value", "previous_value")
    def _compute_delta(self):
        """The model stores the NEW value, not the delta, and ``current_value`` is no
        use to compute it: it is ``related='move_id.value'``, and since
        ``product.value.create`` already ran ``_set_value()`` on the move, once the record
        is saved ``current_value == value`` and the subtraction is always zero. Hence
        ``previous_value``, captured when the adjustment is created."""
        for product_value in self:
            product_value.delta = product_value.value - product_value.previous_value

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            vals if "previous_value" in vals else dict(vals, previous_value=self._get_previous_value(vals))
            for vals in vals_list
        ]
        return super().create(vals_list)

    @api.model
    def _get_previous_value(self, vals):
        """Value in force right before the adjustment about to be created.

        It has to be resolved BEFORE delegating to the standard ``create``, which triggers
        ``_set_value()`` / ``_update_standard_price()`` and leaves the new value both on the
        move and on the product. Recomputing it afterwards with
        ``stock.move._get_value_data(ignore_manual_update=True)`` is no use either: under
        AVCO/FIFO the adjustment already moved the product's ``standard_price``, so that
        "computed value" returns the NEW value and the delta would be zero.
        """
        if vals.get("move_id"):
            return self._get_previous_move_value(vals)
        return self._get_previous_product_value(vals).value

    @api.model
    def _get_previous_move_value(self, vals):
        """Value in force right before an adjustment ON A MOVE: the move's own, as there
        is no earlier adjustment to read it off.

        Its own method, symmetrical to ``_get_previous_product_value`` below, so a module
        extending ``product.value`` with another amount resolves ITS previous value here
        instead of overriding ``create``. A secondary-currency valuation needs exactly
        that (task 58212, ``stock_currency_valuation``: the previous twin of
        ``value_in_currency`` is the move's ``value_in_currency``).
        """
        return self.env["stock.move"].browse(vals["move_id"]).value

    @api.model
    def _get_previous_product_value(self, vals):
        """The adjustment in force right before a product or lot price change — the
        RECORD, not just its value, so a module that extends ``product.value`` with
        another amount reads its own field off it instead of repeating this search. A
        secondary-currency valuation needs exactly that (task 58212,
        ``stock_currency_valuation``: ``value_in_currency`` has no previous twin).

        By the time this create runs, the write on ``standard_price`` has already been
        applied, so the previous price comes from the previous adjustment. Creating a
        product with an initial price already generates a ``product.value``, so in practice
        there almost always is one, and the zero of the very first one is right: the
        variation goes from 0 to the initial price.
        """
        # Scoped to the COMPANY: ``standard_price`` is company-dependent, so a product
        # shared between companies has a different adjustment history in each one, and the
        # search runs in ``sudo()`` (the multi-company record rule does not scope it either),
        # so without this the previous value could come from another company's history and
        # the delta would be wrong. Both standard paths that record a price change pass
        # ``company_id`` (``product.product._change_standard_price``,
        # ``stock.lot._change_standard_price``); the fallback covers a manual create.
        domain = [
            ("move_id", "=", False),
            ("product_id", "=", vals.get("product_id")),
            ("lot_id", "=", vals.get("lot_id", False)),
            ("company_id", "=", vals.get("company_id") or self.env.company.id),
        ]
        # A backdated adjustment (``valuation_date`` in the context of
        # ``_change_standard_price``) is not the last one on record: without this bound the
        # "previous" value would be taken from an adjustment that comes AFTER it.
        if vals.get("date"):
            domain.append(("date", "<=", vals["date"]))
        return self.sudo().search(domain, order="date desc, id desc", limit=1)
