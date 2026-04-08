import json
from collections import defaultdict

from markupsafe import Markup
from odoo import _, api, fields, models


class AccountAutomaticEntryWizard(models.TransientModel):
    _inherit = "account.automatic.entry.wizard"

    action = fields.Selection(
        selection_add=[("change_partner", "Change Partner")],
        ondelete={"change_partner": "cascade"},
    )

    partner_id = fields.Many2one("res.partner", string="To Partner")

    @api.depends(
        "move_line_ids",
        "journal_id",
        "percentage",
        "date",
        "account_type",
        "action",
        "destination_account_id",
        "partner_id",
    )
    def _compute_move_data(self):
        for record in self:
            if record.action == "change_partner":
                record.move_data = json.dumps(record._get_move_dict_vals_change_account())
            else:
                super(AccountAutomaticEntryWizard, record)._compute_move_data()

    def _get_move_dict_vals_change_account(self):
        move_dicts = super()._get_move_dict_vals_change_account()
        if self.action == "change_partner":
            any_updated = False
            # Change labels to reflect the partner change and set the new partner on lines where relevant
            for move in move_dicts:
                if self.partner_id:
                    move["ref"] = _("Transfer entry to %s") % self.partner_id.display_name
                for dummy1, dummy2, line in move.get("line_ids", []):
                    if (
                        self.partner_id
                        and getattr(self, "destination_account_id", None)
                        and line.get("account_id") == self.destination_account_id.id
                    ):
                        line["partner_id"] = self.partner_id.id
                        line["name"] = _("Transfer to %s") % self.partner_id.display_name
                        any_updated = True
                    else:
                        original_partner = self.env["res.partner"].browse(line.get("partner_id"))
                        if original_partner:
                            line["name"] = _("Transfer from %s") % original_partner.display_name

            # If account was not updated, only partner, we need to build move dicts
            if not any_updated and self.partner_id:
                move_dicts = self._build_partner_only_move_dicts()
        return move_dicts

    def _group_lines_by_partner_account_currency(self):
        """Aggregate selected move lines by (partner, account, currency).

        Returns a mapping where keys are tuples (partner, account, currency) and
        values are dicts with aggregated balances, amount_currency and
        analytic_distribution. Keeping this logic separate makes the grouping
        intent explicit and easy to test.
        """
        grouped = defaultdict(lambda: {"balance": 0.0, "amount_currency": 0.0, "analytic_distribution": {}})
        for line in self.move_line_ids:
            key = (line.partner_id, line.account_id, line.currency_id)
            bucket = grouped[key]
            bucket["balance"] += line.balance
            bucket["amount_currency"] += line.amount_currency or 0.0
            if line.analytic_distribution:
                for account_id, distribution in line.analytic_distribution.items():
                    distr = bucket["analytic_distribution"]
                    # Acumular: suma de (balance * porcentaje/100)
                    distr[account_id] = distr.get(account_id, 0) + (line.balance * distribution / 100)
        return grouped

    def _company_rounds_for_balance(self, bal):
        """Return rounded debit/credit amounts in the company currency for a balance.

        The tuple returned is (debit_src, credit_src, debit_dst, credit_dst) and
        follows the same logic used in the core: source lines use inverted sign
        to build counterpart lines, destination lines use the opposite sign.
        """
        company_cur = self.company_id.currency_id
        debit_src = company_cur.round(-bal) if bal < 0 else 0
        credit_src = company_cur.round(bal) if bal > 0 else 0
        debit_dst = company_cur.round(bal) if bal > 0 else 0
        credit_dst = company_cur.round(-bal) if bal < 0 else 0
        return debit_src, credit_src, debit_dst, credit_dst

    def _compute_amount_currency_pair(
        self, currency, total_amount_currency, debit_src, credit_src, debit_dst, credit_dst
    ):
        """Compute signed `amount_currency` for the source and destination lines.

        Rules:
        - If there is no `currency` or no total amount in the foreign currency,
          return (None, None) so the field is omitted.
        - Otherwise, round the total with `currency.round()` and assign the
          absolute value to the side that has a debit, and the negative absolute
          to the side that has a credit. This ensures the sign of
          `amount_currency` matches the debit/credit semantics.
        """
        if not currency or not total_amount_currency:
            return None, None
        total = currency.round(total_amount_currency)
        abs_total = abs(total)

        def _sign_from_debit_credit(debit, credit):
            """Helper to compute signed amount from debit/credit."""
            return abs_total if debit else (-abs_total if credit else 0.0)

        return _sign_from_debit_credit(debit_src, credit_src), _sign_from_debit_credit(debit_dst, credit_dst)

    def _build_partner_only_move_dicts(self):
        """Build move dicts when the user only wants to change the partner (no account change).

        The implementation is split into clear steps:
        1) Group selected move lines by (partner, account, currency).
        2) For each group, compute company-debited/credited amounts and
           the corresponding `amount_currency` values.
        3) Build the two lines (from/to) for each group and assemble a single
           balancing journal entry.
        """
        grouped = self._group_lines_by_partner_account_currency()

        line_vals = []
        for (orig_partner, account, currency), data in grouped.items():
            bal = data["balance"]
            if self.company_id.currency_id.is_zero(bal):
                continue

            debit_src, credit_src, debit_dst, credit_dst = self._company_rounds_for_balance(bal)

            amt_src, amt_dst = self._compute_amount_currency_pair(
                currency, data.get("amount_currency", 0.0), debit_src, credit_src, debit_dst, credit_dst
            )

            # Normalize analytic distribution: compute weighted average (by balance)
            # to obtain percentages summing to ~100. This mirrors the core logic
            # where distribution_amount stores sum(balance * percent) / 100 and
            # is later converted back to a percentage by multiplying by 100 and
            # dividing by the total balance.
            analytic_distribution = {}
            raw_ad = data.get("analytic_distribution") or {}
            if raw_ad:
                denom = data["balance"]
                if denom and not self.company_id.currency_id.is_zero(denom):
                    for acc_id, dist_amount in raw_ad.items():
                        # dist_amount es suma(balance*percent/100), entonces percent = dist_amount/total_balance*100
                        analytic_distribution[acc_id] = (dist_amount / denom) * 100
                else:
                    # If total balance is zero, fallback to empty distribution
                    analytic_distribution = {}

            src_line = {
                "name": _("Transfer from %s") % (orig_partner.display_name if orig_partner else ""),
                "debit": debit_src,
                "credit": credit_src,
                "account_id": account.id,
                "partner_id": orig_partner.id if orig_partner else None,
                "currency_id": currency.id if currency else None,
                "analytic_distribution": analytic_distribution,
            }
            if currency and amt_src is not None:
                src_line["amount_currency"] = amt_src

            dst_line = {
                "name": _("Transfer to %s") % self.partner_id.display_name,
                "debit": debit_dst,
                "credit": credit_dst,
                "account_id": account.id,
                "partner_id": self.partner_id.id,
                "currency_id": currency.id if currency else None,
                "analytic_distribution": analytic_distribution,
            }
            if currency and amt_dst is not None:
                dst_line["amount_currency"] = amt_dst

            line_vals.extend([src_line, dst_line])

        if not line_vals:
            return []

        # In multi-company environments with hierarchies, we need to use the most
        # specific company (deepest child) so that the accounts are accessible
        accounts = self.env["account.account"].browse([l["account_id"] for l in line_vals])
        companies = accounts.company_ids.filtered(lambda c: self.env.company in c.parent_ids) | self.env.company
        lowest_child_company = max(companies, key=lambda company: len(company.parent_ids))

        move = {
            "currency_id": self.journal_id.currency_id.id or self.journal_id.company_id.currency_id.id,
            "move_type": "entry",
            "name": "/",
            "journal_id": self.journal_id.id,
            "company_id": lowest_child_company.id,
            "date": fields.Date.to_string(self.date),
            "ref": _("Transfer entry to %s") % self.partner_id.display_name,
            "line_ids": [(0, 0, l) for l in line_vals],
        }

        return [move]

    @api.depends("move_data")
    def _compute_preview_move_data(self):
        for record in self:
            if record.action == "change_partner":
                preview_columns = [
                    {"field": "account_id", "label": _("Account")},
                    {"field": "name", "label": _("Label")},
                    {"field": "partner_id", "label": _("Partner")},
                    {"field": "debit", "label": _("Debit"), "class": "text-end text-nowrap"},
                    {"field": "credit", "label": _("Credit"), "class": "text-end text-nowrap"},
                ]
                move_vals = json.loads(record.move_data) if record.move_data else []
                preview_vals = []
                for move in move_vals[:4]:
                    preview_vals += [
                        self.env["account.move"]._move_dict_to_preview_vals(move, record.company_id.currency_id)
                    ]
                preview_discarded = max(0, len(move_vals) - len(preview_vals))
                record.preview_move_data = json.dumps(
                    {
                        "groups_vals": preview_vals,
                        "options": {
                            "discarded_number": _("%d moves") % preview_discarded if preview_discarded else False,
                            "columns": preview_columns,
                        },
                    }
                )
            else:
                super(AccountAutomaticEntryWizard, record)._compute_preview_move_data()

    def do_action(self):
        if self.action == "change_partner":
            move_vals = json.loads(self.move_data or "[]")
            if not move_vals:
                return super().do_action()
            return self._do_action_change_account(move_vals)
        return super().do_action()

    def _do_action_change_account(self, move_vals):
        """Override to handle partner change reconciliation correctly."""
        if self.action == "change_partner" and self.partner_id:
            new_move = self.env["account.move"].create(move_vals)
            new_move._post()

            # Group original lines by (partner, currency, account)
            grouped_lines = defaultdict(lambda: self.env["account.move.line"])
            for line in self.move_line_ids:
                grouped_lines[(line.partner_id, line.currency_id, line.account_id)] += line

            # Group new move lines by (partner, currency, account) for efficient lookup
            new_move_lines_by_key = defaultdict(lambda: self.env["account.move.line"])
            for line in new_move.line_ids:
                new_move_lines_by_key[(line.partner_id, line.currency_id, line.account_id)] += line

            # Reconcile original lines with matching lines from new move (same partner/account/currency)
            for (partner, currency, account), lines in grouped_lines.items():
                if account.reconcile:
                    new_lines = new_move_lines_by_key.get((partner, currency, account), self.env["account.move.line"])
                    to_reconcile = lines + new_lines
                    if to_reconcile and len(to_reconcile) > len(lines):  # Only if we found matching lines
                        to_reconcile.reconcile()

            # Log the operation on source moves
            partner_transfer_per_move = defaultdict(lambda: defaultdict(lambda: {"balance": 0, "partner": None}))
            for line in self.move_line_ids:
                key_data = partner_transfer_per_move[line.move_id][line.account_id]
                key_data["balance"] += line.balance
                if not key_data["partner"]:
                    key_data["partner"] = line.partner_id

            for move, data_per_account in partner_transfer_per_move.items():
                message_to_log = self._format_transfer_source_log_partner(data_per_account, new_move)
                if message_to_log:
                    move.message_post(body=message_to_log)

            # Log on target move
            new_move.message_post(body=self._format_new_transfer_move_log_partner(partner_transfer_per_move))

            return {
                "name": _("Transfer"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "account.move",
                "res_id": new_move.id,
            }
        return super()._do_action_change_account(move_vals)

    def _format_new_transfer_move_log_partner(self, partner_transfer_per_move):
        """Format transfer log showing original partner instead of account."""

        transfer_format = Markup("<li>%s, <strong>%%(partner_source_name)s</strong></li>") % _(
            "{amount} ({debit_credit}) from {link}"
        )
        rslt = _(
            "This entry transfers the following amounts to %(destination)s",
            destination=Markup("<strong>%s</strong>") % self.partner_id.display_name,
        ) + Markup("<ul>%(transfer_logs)s</ul>") % {
            "transfer_logs": Markup().join(
                [
                    self._format_strings(
                        transfer_format
                        % {"partner_source_name": data["partner"].display_name if data["partner"] else _("No Partner")},
                        move,
                        data["balance"],
                    )
                    for move, data_per_account in partner_transfer_per_move.items()
                    for account, data in data_per_account.items()
                ],
            ),
        }
        return rslt

    def _format_transfer_source_log_partner(self, data_per_account, transfer_move):
        """Format source log showing target partner for partner transfers."""
        if not data_per_account:
            return None

        transfer_format = Markup(
            _(
                "{amount} ({debit_credit}) from <strong>{partner_source_name}</strong> were transferred to <strong>{partner_target_name}</strong> by {link}"
            )
        )

        return Markup("<ul>%s</ul>") % Markup().join(
            [
                Markup("<li>%s</li>")
                % self._format_strings_partner(
                    transfer_format,
                    transfer_move,
                    data["balance"],
                    data["partner"].display_name if data["partner"] else _("No Partner"),
                    self.partner_id.display_name,
                )
                for account, data in data_per_account.items()
            ]
        )

    def _format_strings_partner(self, string, move, amount, partner_source_name, partner_target_name):
        """Extended _format_strings to include both source and target partner names."""
        from odoo.tools.float_utils import float_repr
        from odoo.tools.misc import format_date, formatLang

        return string.format(
            label=move.name or _("Adjusting Entry"),
            percent=float_repr(self.percentage, 2),
            name=move.name,
            id=move.id,
            amount=formatLang(self.env, abs(amount), currency_obj=self.company_id.currency_id) if amount else "",
            debit_credit=amount < 0 and _("C") or _("D") if amount else None,
            link=move._get_html_link(),
            date=format_date(self.env, move.date),
            new_date=self.date and format_date(self.env, self.date) or _("[Not set]"),
            partner_source_name=partner_source_name,
            partner_target_name=partner_target_name,
        )

    def _format_new_transfer_move_log(self, acc_transfer_per_move):
        """Override to show partner name for partner transfers."""
        if self.action == "change_partner" and self.partner_id:
            # This shouldn't be called for change_partner with partner, but keeping for safety
            return self._format_new_transfer_move_log_partner({})
        return super()._format_new_transfer_move_log(acc_transfer_per_move)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Set destination account based on partner and move types."""
        for record in self:
            if record.action != "change_partner" or not record.partner_id:
                continue

            partner_with_company = record.partner_id.with_company(record.company_id)
            move_types = set(record.move_line_ids.mapped("move_id.move_type"))
            receivable_types = {"out_invoice", "out_refund"}
            payable_types = {"in_invoice", "in_refund"}

            # Determine account type based on move types or selected lines
            if move_types and move_types.issubset(receivable_types):
                acct = partner_with_company.property_account_receivable_id
            elif move_types and move_types.issubset(payable_types):
                acct = partner_with_company.property_account_payable_id
            else:
                # Mixed or unknown: check if any line is receivable to decide
                use_receivable = any(
                    line.account_id.account_type == "asset_receivable" for line in record.move_line_ids
                )
                acct = (
                    partner_with_company.property_account_receivable_id
                    if use_receivable
                    else partner_with_company.property_account_payable_id
                )

            record.destination_account_id = acct.id if acct else False
