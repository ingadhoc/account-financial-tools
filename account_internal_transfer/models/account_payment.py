from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_internal_transfer = fields.Boolean(
        string="Internal Transfer",
        tracking=True,
    )
    destination_company_id = fields.Many2one(
        "res.company",
        compute="_compute_destination_company_id",
        domain='["|", ("id", "parent_of", main_company_id), ("id", "child_of", main_company_id)]',
        store=True,
        readonly=False,
    )
    destination_journal_domain = fields.Binary(compute="_compute_destination_journal_domain")
    destination_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Destination Journal",
        domain="destination_journal_domain",
        check_company=False,
    )
    main_company_id = fields.Many2one(
        "res.company",
        compute="_compute_main_company",
    )
    available_partner_bank_ids = fields.Many2many(compute_sudo=True)
    show_warning = fields.Html(compute="_compute_show_warning")

    @api.depends("company_id", "is_internal_transfer")
    def _compute_destination_company_id(self):
        for rec in self:
            if rec.is_internal_transfer:
                rec.destination_company_id = rec.company_id
            else:
                rec.destination_company_id = False

    @api.depends("destination_company_id", "journal_id")
    def _compute_destination_journal_domain(self):
        for rec in self:
            rec.destination_journal_domain = Domain(
                rec.env["account.journal"]._check_company_domain(rec.destination_company_id)
            ) & Domain([("type", "in", ("bank", "cash", "credit"))])

    @api.constrains("destination_company_id", "destination_journal_id")
    def _check_journal_company(self):
        for rec in self.filtered("destination_journal_id"):
            # Force recompute of the domain to ensure it's up to date
            rec._compute_destination_journal_domain()
            has_cashbox_field = "cashbox_session_id" in rec._fields
            if (not has_cashbox_field or not rec.cashbox_session_id) and rec.destination_journal_id == rec.journal_id:
                raise ValidationError(_("The destination journal must be different from the source journal."))
            if rec.destination_journal_id not in rec.env["account.journal"].search(rec.destination_journal_domain):
                raise ValidationError(
                    _("The selected 'Destination Journal' does not belong to the selected destination company.")
                )

    @api.depends("company_id")
    def _compute_main_company(self):
        for rec in self:
            rec.main_company_id = rec.company_id.parent_id or rec.company_id

    # TO DO: Check in v19+ if odoo delete the paired_internal_transfer_payment_id field, restore the field in this module
    # paired_internal_transfer_payment_id = fields.Many2one('account.payment',
    #     index='btree_not_null',
    #     help="When an internal transfer is posted, a paired payment is created. "
    #     "They are cross referenced through this field", copy=False)

    def _get_name_receipt_report(self, report_xml_id):
        """Method similar to the '_get_name_invoice_report' of l10n_latam_invoice_document
        Basically it allows different localizations to define it's own report
        This method should actually go in a sale_ux module that later can be extended by different localizations
        Another option would be to use report_substitute module and setup a subsitution with a domain
        """
        self.ensure_one()
        if self.is_internal_transfer:
            return "account_internal_transfer.report_account_transfer"
        return report_xml_id

    def _get_aml_default_display_name_list(self):
        values = super()._get_aml_default_display_name_list()
        values = [
            (key, _("Internal Transfer") if self.is_internal_transfer and key == "label" else value)
            for key, value in values
        ]
        return values

    def _get_liquidity_aml_display_name_list(self):
        res = super()._get_liquidity_aml_display_name_list()
        if self.is_internal_transfer:
            if self.payment_type == "inbound":
                return [("transfer_to", _("Transfer to %s", self.journal_id.name))]
            else:  # payment.payment_type == 'outbound':
                return [("transfer_from", _("Transfer from %s", self.journal_id.name))]
        return res

    @api.depends("destination_journal_id", "is_internal_transfer")
    def _compute_available_partner_bank_ids(self):
        super()._compute_available_partner_bank_ids()
        for pay in self:
            if pay.is_internal_transfer:
                pay.available_partner_bank_ids = pay.destination_journal_id.bank_account_id

    @api.depends("is_internal_transfer", "destination_journal_id")
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        for pay in self:
            if pay.is_internal_transfer:
                pay.destination_account_id = pay.destination_journal_id.company_id.transfer_account_id

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super()._get_trigger_fields_to_synchronize()
        return res + ("is_internal_transfer",)

    def _prepare_paired_payment_values(self):
        """Valores para crear el paired payment de una transferencia interna.
        Hookable: account_payment_pro lo extiende para convertir el amount entre monedas.
        """
        self.ensure_one()
        paired_payment_type = "inbound" if self.payment_type == "outbound" else "outbound"
        return {
            "journal_id": self.destination_journal_id.id,
            "currency_id": (self.destination_journal_id.currency_id or self.company_currency_id).id,
            "company_id": self.destination_company_id.id,
            "destination_company_id": self.company_id.id,
            "destination_journal_id": self.journal_id.id,
            "payment_type": paired_payment_type,
            "payment_method_line_id": self.destination_journal_id._get_available_payment_method_lines(
                paired_payment_type
            )[:1].id,
            "move_id": None,
            "memo": self.memo,
            "paired_internal_transfer_payment_id": self.id,
            "date": self.date,
        }

    def _create_paired_internal_transfer_payment(self):
        """When an internal transfer is posted, a paired payment is created
        with opposite payment_type and swapped journal_id & destination_journal_id.
        Both payments liquidity transfer lines are then reconciled.
        """
        if self.filtered(lambda x: x.move_id.state == "draft"):
            raise UserError(
                _(
                    "We couldn't create the paired payment because the journal entry of the original payment is in draft state."
                )
            )
        for payment in self:
            paired_payment = payment.copy(payment._prepare_paired_payment_values())
            # The payment method line ID in 'paired_payment' needs to be computed manually,
            # as it does not compute automatically.
            # This ensures not to use the same payment method line ID of the original transfer payment.
            paired_payment._compute_payment_method_line_id()
            if (
                not payment.payment_method_line_id.payment_account_id
                or not paired_payment.payment_method_line_id.payment_account_id
            ):
                raise ValidationError(
                    _("The origin or destination payment methods do not have an outstanding account.")
                )
            paired_payment.filtered(lambda p: not p.move_id)._generate_journal_entry(
                # Force the exact ARS balance from the original transfer line to avoid
                # rounding discrepancies when both journals are in different foreign currencies
                # (e.g. USD → EUR), which would prevent full reconciliation of the bridge lines.
                force_balance=abs(
                    sum(
                        payment.move_id.line_ids.filtered(
                            lambda l: l.account_id == payment.destination_account_id
                        ).mapped("balance")
                    )
                )
            )
            paired_payment.move_id._post(soft=False)
            payment.paired_internal_transfer_payment_id = paired_payment
            body = _("This payment has been created from:") + payment._get_html_link()
            paired_payment.message_post(body=body)
            body = _("A second payment has been created:") + paired_payment._get_html_link()
            payment.message_post(body=body)

            lines = (payment.move_id.line_ids + paired_payment.move_id.line_ids).filtered(
                lambda l: l.account_id == payment.destination_account_id and not l.reconciled
            )
            lines.reconcile()

    def action_post(self):
        super().action_post()
        self.filtered(
            lambda pay: pay.is_internal_transfer and not pay.paired_internal_transfer_payment_id
        )._create_paired_internal_transfer_payment()

    def action_open_destination_journal(self):
        """Redirect the user to this destination journal.
        :return:    An action on account.move.
        """
        self.ensure_one()

        action = {
            "name": _("Destination journal"),
            "type": "ir.actions.act_window",
            "res_model": "account.journal",
            "context": {"create": False},
            "view_mode": "form",
            "target": "new",
            "res_id": self.destination_journal_id.id,
        }
        return action

    @api.depends("is_internal_transfer")
    def _compute_partner_id(self):
        super()._compute_partner_id()
        for pay in self.filtered("is_internal_transfer"):
            pay.partner_id = False

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance
        )

        if (
            # This is to avoid dependency on payment_pro
            "amount_company_currency" in self._fields
            and self.is_internal_transfer
            # Payment journal is in company currency (either not set or explicitly set to company currency)
            and (not self.journal_id.currency_id or self.journal_id.currency_id == self.company_id.currency_id)
            and self.destination_journal_id.currency_id  # Destination journal has a different currency
            and self.destination_journal_id.currency_id != self.company_id.currency_id
        ):
            for line_vals in line_vals_list:
                if "amount_currency" in line_vals:
                    # Set the currency to the company's currency
                    line_vals["currency_id"] = self.company_id.currency_id.id
                    # Adjust the amount_currency based on the balance
                    if line_vals["balance"] > 0:
                        line_vals["amount_currency"] = self.amount_company_currency
                    elif line_vals["balance"] < 0:
                        line_vals["amount_currency"] = -self.amount_company_currency
                    else:
                        # When balance is zero, ensure amount_currency is neutral
                        line_vals["amount_currency"] = 0.0
        return line_vals_list

    def write(self, vals):
        res = super().write(vals)
        # Avoid recursion when updating paired payments
        if self.env.context.get("skip_paired_payment_update"):
            return res

        # Update paired payment when amount or journal changes
        for payment in self.filtered(lambda p: p.is_internal_transfer and p.paired_internal_transfer_payment_id):
            paired_payment = payment.paired_internal_transfer_payment_id
            updates = {}

            # Sync amount
            if "amount" in vals and payment.amount != paired_payment.amount:
                updates["amount"] = payment.amount

            # Sync journals (swapped relationship)
            if "journal_id" in vals and payment.journal_id != paired_payment.destination_journal_id:
                updates["destination_journal_id"] = payment.journal_id.id

            if "destination_journal_id" in vals and payment.destination_journal_id != paired_payment.journal_id:
                updates["journal_id"] = payment.destination_journal_id.id

            # Apply updates to paired payment
            if updates:
                paired_payment.with_context(skip_paired_payment_update=True).write(updates)

        return res

    @api.depends("state", "paired_internal_transfer_payment_id.state")
    def _compute_show_warning(self):
        for pay in self:
            paired_pay = pay.paired_internal_transfer_payment_id
            if (
                pay.is_internal_transfer
                and paired_pay
                and paired_pay.state != pay.state
                and (pay.state in ["draft", "canceled"] or paired_pay.state in ["draft", "canceled"])
            ):
                state_labels = dict(pay._fields["state"]._description_selection(pay.env))
                base_url = pay.env["ir.config_parameter"].sudo().get_param("web.base.url")
                action_url = f"{base_url}/web#id={paired_pay.id}&model=account.payment&view_type=form"
                # Escape all dynamic values to prevent XSS
                pay_state = escape(state_labels.get(pay.state, pay.state))
                paired_state = escape(state_labels.get(paired_pay.state, paired_pay.state))
                safe_url = escape(action_url)
                pay.show_warning = Markup(
                    _(
                        '<div class="alert alert-warning" role="alert">'
                        '<i class="fa fa-exclamation-triangle"></i> '
                        "This payment is in <strong>%s</strong> state but the paired one is in <strong>%s</strong> state. "
                        "Ensure both are in the same state when finished making changes. "
                        '<a href="%s" class="btn btn-sm btn-warning" style="margin-left: 10px;">'
                        '<i class="fa fa-external-link"></i> Go to Paired Payment'
                        "</a>"
                        "</div>"
                    )
                ) % (pay_state, paired_state, safe_url)
            else:
                pay.show_warning = ""

    def action_open_paired_payment(self):
        """Navigate to the paired internal transfer payment."""
        self.ensure_one()
        if not self.paired_internal_transfer_payment_id:
            return

        return {
            "name": _("Paired Payment"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "form",
            "res_id": self.paired_internal_transfer_payment_id.id,
            "target": "current",
        }
