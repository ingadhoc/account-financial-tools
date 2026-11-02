import logging

from odoo import Command, _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    next_surcharge_date = fields.Date(compute="_compute_next_surcharge", store=True)
    next_surcharge_percent = fields.Float(compute="_compute_next_surcharge", store=True)
    avoid_surcharge_invoice = fields.Boolean()
    surcharge_id = fields.Many2one(
        "account.payment.term.surcharge",
        string="Payment Term Surcharge",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
    )

    def _cron_recurring_surcharges_invoices(self, batch_size=60):
        current_date = fields.Date.context_today(self)
        domain = [
            ("next_surcharge_date", "<=", current_date),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("avoid_surcharge_invoice", "=", False),
        ]
        _logger.info(
            "Running Surcharges Invoices Cron Job, pendientes por procesar %s facturas" % self.search_count(domain)
        )
        to_create = self.search(domain)
        to_create[:batch_size].create_surcharges_invoices()
        if len(to_create) > batch_size:
            self.env.ref("account_payment_term_surcharge.cron_recurring_surcharges_invoices")._trigger()

    def create_surcharges_invoices(self):
        invoice_with_errors = []
        current_date = fields.Date.context_today(self)
        for rec in self:
            pending = rec._get_pending_surcharges()
            if not pending or pending[0][0] > current_date:
                continue
            _logger.info("Creating Surcharges Invoices (id: %s, company: %s)", rec.id, rec.company_id.name)
            try:
                rec.create_surcharge_invoice(pending[0][1])
                if not tools.config["test_enable"]:
                    rec.env.cr.commit()
            except:
                invoice_with_errors.append(rec.id)
                rec.avoid_surcharge_invoice = True
                _logger.error(f"Something went wrong creating the surcharge invoice from the invoice id:{rec.id}")
                message_body = _(
                    "Something went wrong creating the surcharge invoice from this invoice. Please take a look on it."
                )
                partner_ids = rec.message_partner_ids.filtered(lambda x: not x.partner_share)
                rec.message_post(body=message_body, partner_ids=partner_ids.ids, subtype_xmlid="mail.mt_note")
                if not tools.config["test_enable"]:
                    rec.env.cr.commit()
                continue
        if invoice_with_errors:
            error_message = _("We couldn't run surcharges cron job in the following invoice: %s.") % invoice_with_errors
            raise UserError(error_message)

    def create_surcharge_invoice(self, surcharge):
        self.ensure_one()
        product = self.company_id.payment_term_surcharge_product_id
        if not product:
            raise UserError(
                "Atención, debes configurar un producto por defecto para que aplique a la hora de crear las facturas de recargo"
            )
        surcharge_date = surcharge._calculate_date(self.invoice_date)
        surcharge_percent = surcharge.surcharge
        debt = self.amount_residual
        move_debit_note_wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=self.ids)
            .create(
                {
                    "date": surcharge_date,
                    "reason": product.name,
                }
            )
        )
        debit_note = self.env["account.move"].browse(move_debit_note_wiz.create_debit().get("res_id"))
        debit_note.surcharge_id = surcharge
        debit_note.narration = product.name + ".\n" + self.prepare_info(surcharge_date, debt, surcharge_percent)
        self._add_surcharge_line(debit_note, product, debt, surcharge_date, surcharge_percent)
        if self.company_id.payment_term_surcharge_invoice_auto_post:
            try:
                debit_note.action_post()
            except Exception as exp:
                _logger.error("Something went wrong validating " f"surcharge invoice: {exp}")
                raise exp
        self._compute_next_surcharge()

    def prepare_info(self, to_date, debt, surcharge):
        self.ensure_one()
        lang_code = self.env.context.get("lang", self.env.user.lang)
        lang = self.env["res.lang"]._lang_get(lang_code)
        date_format = lang.date_format
        to_date_format = to_date.strftime(date_format)
        res = _("Deuda Vencida al %s: %s\n" "Tasa de interés: %s") % (to_date_format, debt, surcharge)
        return res

    def _add_surcharge_line(self, debit_note, product, debt, to_date, surcharge):
        self.ensure_one()
        comment = self.prepare_info(to_date, debt, surcharge)
        debit_note = debit_note.with_context(check_move_validity=False)
        line_vals = [
            Command.create(
                {
                    "product_id": product.id,
                    "price_unit": (surcharge / 100) * debt,
                    "name": product.name + ".\n" + comment,
                }
            )
        ]
        debit_note.write({"invoice_line_ids": line_vals, "is_move_sent": True})

    def _get_pending_surcharges(self):
        """Return the (date, surcharge) pairs of the payment term not charged yet, sorted by date.
        A surcharge is charged when a debit note of the invoice was created for it, in any state."""
        self.ensure_one()
        debit_notes = self.debit_note_ids
        product = self.company_id.payment_term_surcharge_product_id
        # Surcharge debit notes created before surcharge_id existed are matched by date
        legacy_dates = debit_notes.filtered(
            lambda n: not n.surcharge_id and product in n.invoice_line_ids.product_id
        ).mapped("invoice_date")
        pending = []
        for surcharge in self.invoice_payment_term_id.surcharge_ids - debit_notes.surcharge_id:
            surcharge_date = surcharge._calculate_date(self.invoice_date)
            if surcharge_date not in legacy_dates:
                pending.append((surcharge_date, surcharge))
        return sorted(pending, key=lambda p: p[0])

    @api.depends(
        "invoice_date",
        "invoice_payment_term_id.surcharge_ids.option",
        "invoice_payment_term_id.surcharge_ids.days",
        "invoice_payment_term_id.surcharge_ids.day_of_the_month",
        "invoice_payment_term_id.surcharge_ids.surcharge",
        "debit_note_ids.surcharge_id",
    )
    def _compute_next_surcharge(self):
        for rec in self:
            pending = rec._get_pending_surcharges()
            rec.next_surcharge_date = pending[0][0] if pending else False
            rec.next_surcharge_percent = pending[0][1].surcharge if pending else False

    def action_post(self):
        res = super().action_post()
        self.avoid_surcharge_invoice = False
        return res

    def action_send_invoice_mail(self):
        """Filtramos solamente las facturas que no cuenta con el is_move_sent seteado en True"""
        self = self.filtered(lambda x: not x.is_move_sent)
        super().action_send_invoice_mail()
