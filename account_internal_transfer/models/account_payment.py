from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_internal_transfer = fields.Boolean(
        string="Internal Transfer",
        tracking=True,
    )

    destination_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Destination Journal",
        domain="[('type', 'in', ('bank','cash','credit')), ('id', '!=', journal_id),('company_id', 'child_of', main_company_id)]",
        check_company=False,
    )
    main_company_id = fields.Many2one(
        "res.company",
        compute="_compute_main_company",
    )
    available_partner_bank_ids = fields.Many2many(compute_sudo=True)

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

    def _create_paired_internal_transfer_payment(self):
        """When an internal transfer is posted, a paired payment is created
        with opposite payment_type and swapped journal_id & destination_journal_id.
        Both payments liquidity transfer lines are then reconciled.
        """
        for payment in self:
            paired_payment_type = "inbound" if payment.payment_type == "outbound" else "outbound"
            paired_payment = payment.copy(
                {
                    "journal_id": payment.destination_journal_id.id,
                    "company_id": payment.destination_journal_id.company_id.id,
                    "destination_journal_id": payment.journal_id.id,
                    "payment_type": paired_payment_type,
                    "payment_method_line_id": payment.destination_journal_id._get_available_payment_method_lines(
                        paired_payment_type
                    )[:1].id,
                    "move_id": None,
                    "memo": payment.memo,
                    "paired_internal_transfer_payment_id": payment.id,
                    "date": payment.date,
                }
            )
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
            paired_payment.filtered(lambda p: not p.move_id)._generate_journal_entry()
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
