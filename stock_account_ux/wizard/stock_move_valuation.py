from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.stock_move_line import PARTIAL_LINES_CTX


class StockMoveValuation(models.TransientModel):
    """Book selected stock moves without waiting for the global closing.

    The entry is grouped by the valuation accounts the product categories define (the
    same account resolution the three report sections use) and by product, and it is
    linked to the moves so they cannot be valued twice.
    """

    _name = "stock.move.valuation"
    _description = "Value Stock Moves"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        help="Date of the valuation entry.",
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        required=True,
        check_company=True,
        default=lambda self: self.env.company.account_stock_journal_id,
        domain="[('company_id', '=', company_id)]",
    )
    move_ids = fields.Many2many(
        comodel_name="stock.move",
        string="Stock Moves",
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="stock.move.valuation.line",
        inverse_name="valuation_id",
        string="Journal Items",
        compute="_compute_line_ids",
    )
    total = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_line_ids",
        help="Total of the entry to post.",
    )
    excluded_warning = fields.Text(readonly=True)
    partial_lines_warning = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Already valued moves are left OUT of the selection, so the product's booked
        value is not doubled. Which ones and why is reported instead of raising: in a
        bulk selection some already valued moves are bound to slip in, and stopping
        everything would force the user to build the selection again."""
        defaults = super().default_get(fields_list)
        move_ids = self.env.context.get("default_move_ids") or defaults.get("move_ids") or []
        if isinstance(move_ids, int):
            move_ids = [move_ids]
        moves = self.env["stock.move"].browse(move_ids).exists()
        if not moves:
            return defaults
        already_valued = moves.filtered("related_account_move_id")
        valuable = moves - already_valued
        if not valuable:
            raise UserError(
                self.env._(
                    "The selected moves are already booked. Valuing them again would double "
                    "the product's booked value."
                )
            )
        defaults["move_ids"] = [fields.Command.set(valuable.ids)]
        if already_valued:
            defaults["excluded_warning"] = self.env._(
                "%(count)s moves were excluded because they already have a valuation entry "
                "(valuing them again would double the product's booked value): "
                "%(references)s",
                count=len(already_valued),
                references=", ".join(already_valued[:10]._get_valuation_labels()),
            )
        # Valuing from Moves History, which lists move lines: when only some lines of a
        # move are selected, the move is valued whole.
        partial_ids = set(self.env.context.get(PARTIAL_LINES_CTX) or [])
        partially_selected = valuable.filtered(lambda m: m.id in partial_ids)
        if partially_selected:
            defaults["partial_lines_warning"] = self.env._(
                "You selected only some lines of %(count)s moves. Valuation goes by move, so "
                "they are valued whole: %(references)s",
                count=len(partially_selected),
                references=", ".join(partially_selected[:10]._get_valuation_labels()),
            )
        return defaults

    @api.depends("move_ids", "company_id")
    def _compute_line_ids(self):
        for wizard in self:
            aml_vals_list = wizard._get_account_move_line_vals()
            wizard.line_ids = [fields.Command.create(wizard._get_draft_line_vals(vals)) for vals in aml_vals_list]
            wizard.total = sum(vals["debit"] for vals in aml_vals_list)

    def _get_draft_line_vals(self, aml_vals):
        """One line of the draft shown before posting, out of the journal item vals.

        Its own method so a module adding a column to ``stock.move.valuation.line`` fills
        it here instead of rewriting ``_compute_line_ids``. A secondary-currency valuation
        is the case (task 58212, ``stock_currency_valuation``: the amount in the other
        currency has to be visible in the draft too).
        """
        return {
            "account_id": aml_vals["account_id"],
            "product_id": aml_vals.get("product_id"),
            "name": aml_vals["name"],
            "debit": aml_vals["debit"],
            "credit": aml_vals["credit"],
        }

    def _get_balances_by_accounts(self):
        """Balance to book per ``(valuation account, counterpart, product)``.

        What a move contributes is measured with the inventory criterion
        (``stock.move._get_inventory_value``): incoming moves add to the asset, outgoing
        ones subtract. The valuation account comes from the product's category (via
        ``_get_product_accounts``) and the counterpart from the account itself
        (``account_stock_variation_id``), falling back to the company expense account,
        as in the standard closing.

        The grouping includes the PRODUCT: the accounts are still the categories', but
        every line is attributed to its product. That ``product_id`` is what later lets
        the report's Initial Balance honour the product filter — the standard periodic
        closing leaves it empty, which is why its balance cannot be filtered.
        """
        self.ensure_one()
        balances = defaultdict(float)
        # The accounts are the product CATEGORY's, so resolving them move by move repeats
        # the same work: on a bulk selection several moves share the product. Cached per
        # product instead.
        accounts_by_product = {}
        for move in self.move_ids:
            product = move.product_id
            if product.id not in accounts_by_product:
                accounts_by_product[product.id] = product.with_company(self.company_id)._get_product_accounts()
            accounts = accounts_by_product[product.id]
            valuation_account = accounts.get("stock_valuation")
            if not valuation_account:
                continue
            counterpart = valuation_account.account_stock_variation_id or self.company_id.expense_account_id
            if not counterpart:
                continue
            value = move._get_inventory_value()
            key = self._get_balance_key(move, valuation_account, counterpart)
            balances[key] += value if move.is_in else -value
        return balances

    def _get_balance_key(self, move, valuation_account, counterpart):
        """What makes two moves collapse into the SAME journal item.

        A method so a module can widen the key: two moves of one product only add up when
        everything the entry has to state about them matches. A secondary-currency
        valuation is the case (task 58212, ``stock_currency_valuation``) — same product at
        two different rates cannot become one line. Whatever is added here has to be read
        back in ``_get_account_move_line_vals``, which unpacks this tuple.
        """
        return (valuation_account, counterpart, move.product_id)

    def _get_account_move_line_vals(self):
        self.ensure_one()
        aml_vals_list = []
        for key, balance in self._get_balances_by_accounts().items():
            if self.company_id.currency_id.is_zero(balance):
                continue
            aml_vals_list += self._get_aml_vals_for_key(key, balance)
        return aml_vals_list

    def _get_aml_vals_for_key(self, key, balance):
        """The journal items of ONE grouped balance, key included.

        Its own method so a module that widened the key in ``_get_balance_key`` can add to
        the line what that widening states — an amount in another currency, for one (task
        58212, ``stock_currency_valuation``). Doing it from
        ``_get_account_move_line_vals`` is not possible: there the lines arrive already
        flattened and there is no way back to the key each one came from.
        """
        valuation_account, counterpart, product = key[0], key[1], key[2]
        aml_vals = self.company_id._prepare_inventory_aml_vals(
            valuation_account,
            counterpart,
            balance,
            self.env._("Stock Valuation - [%(account)s]", account=valuation_account.display_name),
            product_id=product.id,
        )
        # The valuation account is the category's, so an entry over moves of several
        # products has several lines on it. Naming the product in the LABEL is what
        # tells the user which line is whose; the counterpart keeps the generic label
        # (functional feedback, task 64440). ``_prepare_inventory_aml_vals`` swaps the
        # legs when the balance is negative, hence matching by account instead of by
        # position.
        for vals in aml_vals:
            if vals["account_id"] == valuation_account.id:
                vals["name"] = self.env._("%(label)s - %(product)s", label=vals["name"], product=product.display_name)
        return aml_vals

    def action_post(self):
        self.ensure_one()
        aml_vals_list = self._get_account_move_line_vals()
        if not aml_vals_list:
            raise UserError(self.env._("The selected moves have no value to book."))
        account_move = self.env["account.move"].create(
            {
                "journal_id": self.journal_id.id,
                "date": self.date,
                "ref": self.env._("Stock Valuation"),
                "company_id": self.company_id.id,
                "line_ids": [fields.Command.create(vals) for vals in aml_vals_list],
            }
        )
        account_move._post()
        # Linking the entry to the valued moves is what prevents valuing them again and
        # what takes them out of the report's pending variation, and out of the scope of
        # the periodic closing.
        self.move_ids.account_move_id = account_move.id
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Journal Entry"),
            "res_model": "account.move",
            "res_id": account_move.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }


class StockMoveValuationLine(models.TransientModel):
    _name = "stock.move.valuation.line"
    _description = "Value Stock Moves Line"

    valuation_id = fields.Many2one("stock.move.valuation", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="valuation_id.currency_id")
    account_id = fields.Many2one("account.account", string="Account", readonly=True)
    # The line is attributed to the product (see ``_get_balances_by_accounts``), so the
    # draft shows it: without this column several lines of the same account would look
    # identical.
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    name = fields.Char(string="Label", readonly=True)
    debit = fields.Monetary(currency_field="currency_id", readonly=True)
    credit = fields.Monetary(currency_field="currency_id", readonly=True)
