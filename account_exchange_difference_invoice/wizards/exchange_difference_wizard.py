from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ExchangeDifferenceWizard(models.TransientModel):
    _name = "account.exchange.difference.wizard"
    _description = "Exchange Difference Wizard"
    _check_company_auto = True

    line_ids = fields.One2many("account.exchange.difference.line.wizard", "wizard_id", string="Lines")
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        required=True,
        domain=[("type", "=", "sale")],
        check_company=True,
    )
    fiscal_position = fields.Selection(
        [("automatic", "Automatic"), ("manual", "Manual")],
        default="automatic",
        string="Fiscal Position Mode",
        required=True,
        help="If automatic, fiscal position will be auto detected for each customer, if manual you can force one or none fiscal position.",
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        help="Fiscal position to use for all the customers.",
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if not self.env.company.exchange_difference_product:
            raise UserError(
                _(
                    "To use this functionality, you must configure a product for exchange differences in the company settings."
                )
            )

        if "move_line_ids" in self.env.context:
            move_line_ids = self.env.context["move_line_ids"]

            if move_line_ids:
                # Recuperamos las líneas de movimiento
                # por ahora directamente filtramos los que ya se procesaron
                move_lines = self.env["account.move.line"].search(
                    [
                        ("move_id.exchange_reversal_id", "=", False),
                        ("move_id.exchange_reversed_move_ids", "=", False),
                    ]
                    + [("id", "in", move_line_ids)]
                )

                self._validate_entries_to_process(move_lines)

                grouped = move_lines.grouped(lambda r: r.partner_id.id)

                lines_vals = []
                for partner_id, recs in grouped.items():
                    partner = self.env["res.partner"].browse(partner_id)
                    balance = sum(recs.mapped("balance"))

                    lines_vals.append(
                        (
                            0,
                            0,
                            {
                                "partner_id": partner.id,
                                "balance": balance,
                            },
                        ),
                    )

                # All lines are from the same company
                res["company_id"] = move_lines[0].company_id.id
                res["line_ids"] = lines_vals
        return res

    def action_create_debit_credit_notes(self):
        moves = self.line_ids._create_invoice_and_reconcile(self.journal_id)

        # Solo va a la vista de notas de debito/credito si se generó alguna
        if any(line.balance != 0 for line in self.line_ids):
            return moves.filtered(lambda x: x.move_type != "entry")._get_records_action(name="Debit/Credit Notes")

        # Sino recarga la vista de Exchange entries (como si hiciera clic en el menú)
        return self.env.ref("account_exchange_difference_invoice.action_exchange_difference_server").read()[0]

    def _validate_entries_to_process(self, move_lines):
        if not move_lines:
            raise UserError(_("There are no entries to process or they have already been processed"))

        if len(move_lines.mapped("company_id")) > 1:
            raise UserError(_("All entries must belong to the same company"))


class ExchangeDifferenceWizardLine(models.TransientModel):
    _name = "account.exchange.difference.line.wizard"
    _description = "Exchange Difference Line Wizard"

    wizard_id = fields.Many2one("account.exchange.difference.wizard", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner")
    company_currency_id = fields.Many2one(related="wizard_id.company_id.currency_id", string="Company Currency")
    balance = fields.Monetary(currency_field="company_currency_id")
    show_warning = fields.Html(compute="_compute_show_warning")

    # TODO: agregamos periodo?

    def _create_invoice_and_reconcile(self, journal):
        all_moves = self.env["account.move"]

        amls = self.env["account.move.line"].browse(self.env.context.get("move_line_ids", []))
        partner_to_moves = {
            partner_id: lines.mapped("move_id") for partner_id, lines in amls.grouped(lambda r: r.partner_id.id).items()
        }

        for rec in self:
            rec_account = rec.with_company(rec.wizard_id.company_id)._get_receivable_account()
            move = self.env["account.move"].create(
                rec._prepare_reversal(self.env.company.currency_exchange_journal_id, rec_account)
            )

            exch_moves = partner_to_moves.get(rec.partner_id.id, self.env["account.move"])

            exch_moves.write({"exchange_reversal_id": move.id})

            move.action_post()

            invoice_vals = rec._prepare_debit_credit_note(exch_moves, journal, rec_account)

            if rec.balance == 0.0:
                continue

            debit_credit_note = (
                self.env["account.move"]
                .with_context(exchange_diff_account_receivable_id=rec_account.id)
                .create(invoice_vals)
            )
            if debit_credit_note.currency_id.round(debit_credit_note.amount_total) < 0:
                # switch to credit note if the final total is negative
                debit_credit_note.action_switch_move_type()

            # estamos dejando el link por ahora solo para facilitar el computado del campo que agregamos en account.move.line
            # pero si terminamos yendo por otra usabilidad este link no parece ser necesario (Ya está la conciliación nativa de odoo)
            move.exchange_reversal_id = debit_credit_note.id
            # en los asientos que mandamos a crear factura dejamos referencia de la factura para que se vea en recibo y otros lugares
            amls.mapped("move_id").write({"ref": debit_credit_note.name})

            # Mandamos un mensaje a los pagos relacionados con la diferencia de cambio
            # para que quede constancia de la conciliación con la nota de débito/crédito
            am_id = amls.filtered(lambda x: x.partner_id == rec.partner_id).mapped("move_id.id")
            partial_reconcile = self.env["account.partial.reconcile"].search([("exchange_move_id.id", "=", am_id)])
            related_payments = (
                (partial_reconcile.mapped("debit_move_id") + partial_reconcile.mapped("credit_move_id"))
                .filtered(lambda l: l.move_type == "entry")
                .mapped("payment_id")
            )
            if related_payments:
                for payment in related_payments:
                    payment.message_post(
                        body=_(
                            "This payment has been reconciled with this %s",
                            debit_credit_note._get_html_link(title="exchange difference note"),
                        )
                    )

                body = _(
                    "This debit/credit note has been reconciled with the following payments:%s",
                    Markup("<br/><ul>%s</ul>")
                    % Markup().join(Markup("<li>%s</li>") % p._get_html_link() for p in related_payments),
                )
                debit_credit_note.message_post(body=body)

            all_moves += move + debit_credit_note
        return all_moves

    def _prepare_reversal(self, journal, rec_account):
        """
        Retorna un diccionario con los datos para crear la factura de reversión de la diferencia de cambio
        """
        self.ensure_one()

        company = self.wizard_id.company_id
        currency = self.wizard_id.company_id.currency_id
        partner = self.partner_id
        balance = self.balance
        exchange_line_account = self.env["account.move.line"]._get_exchange_account(company, balance)

        line_vals = [
            {
                "name": _("Currency exchange rate difference"),
                "debit": -balance if balance < 0.0 else 0.0,
                "credit": balance if balance > 0.0 else 0.0,
                "amount_currency": -balance,
                "account_id": rec_account.id,
                "currency_id": currency.id,
                "partner_id": partner.id,
            },
            {
                "name": _("Currency exchange rate difference"),
                "debit": balance if balance > 0.0 else 0.0,
                "credit": -balance if balance < 0.0 else 0.0,
                "amount_currency": balance,
                "account_id": exchange_line_account.id,
                "currency_id": currency.id,
                "partner_id": partner.id,
            },
        ]

        return {
            "move_type": "entry",
            "name": "/",  # do not trigger the compute name before posting as it will most likely be posted immediately after
            "journal_id": journal.id,
            "line_ids": [(0, 0, vals) for vals in line_vals],
        }

    def _get_receivable_account(self):
        # si estamos haciendo nc/nd de cuenta con otra moneda, busamos cuenta por defecto de la cia para no tener
        # la constraint de comprobante en otra moneda
        rec_account = self.partner_id.with_company(self.wizard_id.company_id).property_account_receivable_id
        if rec_account.currency_id:
            rec_account = (
                self.env["res.partner"]
                ._fields["property_account_receivable_id"]
                .get_company_dependent_fallback(self.env["res.partner"])
            )
            # simil pos con _get_balancing_account pero por ahora estamos evitando agregar un settig
            # es muy raro que la cuenta por defecto este en una divisa pero de ser necesario podriamos agregar una cuenta contable
            if rec_account.currency_id:
                raise UserError(
                    _(
                        "To use the exchange difference wizard, the partner's receivable account must not be set to a foreign currency."
                    )
                )

        return rec_account

    def _prepare_invoice_lines_by_taxes(self, invoice_lines, account, amount):
        """
        Agrupa las líneas de factura por combinación de impuestos y prorratea el balance.
        Retorna una lista de tuplas (0, 0, vals) para crear las líneas de la nota de débito/crédito.
        """
        self.ensure_one()

        product = self.env.company.exchange_difference_product
        partner = self.partner_id

        # Si no hay líneas de factura, retornamos una única línea con el balance total
        if not invoice_lines:
            return [
                (
                    0,
                    0,
                    {
                        "account_id": account.id,
                        "quantity": 1.0,
                        "price_unit": self.balance,
                        "partner_id": partner.id,
                        "product_id": product.id,
                    },
                )
            ]

        # En contexto de localización argentina, filtramos los impuestos que no son IVA
        # (aquellos cuyo tax_group_id no tiene l10n_ar_vat_afip_code seteado)
        is_argentina = self.env["account.tax.group"]._fields.get("l10n_ar_vat_afip_code")

        tax_groups = {}
        for line in invoice_lines:
            if is_argentina:
                # Solo consideramos impuestos de IVA (con l10n_ar_vat_afip_code seteado)
                taxes = line.tax_ids.filtered("tax_group_id.l10n_ar_vat_afip_code")
                other_taxes = line.tax_ids - taxes
            else:
                taxes = line.tax_ids
            tax_key = frozenset(taxes.ids)
            if tax_key not in tax_groups:
                tax_groups[tax_key] = {
                    "tax_ids": taxes,
                    "subtotal": 0.0,
                }
            if not self.wizard_id.fiscal_position_id:
                tax_groups[tax_key]["subtotal"] += line.price_total
            else:
                tax_groups[tax_key]["subtotal"] += line.price_total - sum(other_taxes.mapped("amount"))

        # Calcular el total de subtotales para el prorrateo
        total_subtotal = sum(group["subtotal"] for group in tax_groups.values())
        # total_subtotal = sum(invoice_lines.mapped("price_total"))

        # Si el total es cero, distribuimos equitativamente
        if total_subtotal == 0:
            return [
                (
                    0,
                    0,
                    {
                        "account_id": account.id,
                        "quantity": 1.0,
                        "price_unit": amount,
                        "partner_id": partner.id,
                        "product_id": product.id,
                    },
                )
            ]

        # Crear las líneas prorrateadas
        invoice_line_vals = []
        remaining_balance = amount
        groups_list = list(tax_groups.values())

        for i, group in enumerate(groups_list):
            if i == len(groups_list) - 1:
                # Última línea: usar el saldo restante para evitar diferencias de redondeo
                price_unit = remaining_balance
            else:
                # Prorratear según el peso del subtotal
                proportion = group["subtotal"] / total_subtotal
                price_unit = self.wizard_id.company_id.currency_id.round(amount * proportion)
                remaining_balance -= price_unit

            invoice_line_vals.append(
                (
                    0,
                    0,
                    {
                        "account_id": account.id,
                        "quantity": 1.0,
                        "price_unit": price_unit,
                        "partner_id": partner.id,
                        "product_id": product.id,
                        "tax_ids": [(6, 0, group["tax_ids"].ids)],
                    },
                )
            )

        return invoice_line_vals

    def _prepare_debit_credit_note(self, exch_moves, journal, rec_account):
        """
        Retorna un diccionario con los datos para crear la nota de débito/crédito
        Prorratea el balance entre las diferentes combinaciones de impuestos presentes en las líneas de factura
        """
        self.ensure_one()

        company = self.wizard_id.company_id
        partner = self.partner_id
        account = self.env["account.move.line"]._get_exchange_account(company, self.balance)

        # approach si hacemos una sola linea
        # partial_reconciles = self.env["account.partial.reconcile"].search(
        #     [("exchange_move_id", "in", exch_moves.ids)]
        # )
        # invoice_lines = (partial_reconciles.mapped("debit_move_id") + partial_reconciles.mapped("credit_move_id")).mapped("move_id").filtered(lambda move: move.is_sale_document()).mapped("invoice_line_ids")
        # invoice_line_vals = self._prepare_invoice_lines_by_taxes(invoice_lines, account, self.balance)

        # en este approach iteramos sobre cada exhcange diff y generamos lineas para cada grupo de impuestos
        invoice_line_vals = []
        for exchange_move in exch_moves:
            partial_reconcile = self.env["account.partial.reconcile"].search(
                [("exchange_move_id", "=", exchange_move.ids)]
            )
            invoice_lines = (
                (partial_reconcile.debit_move_id + partial_reconcile.credit_move_id)
                .mapped("move_id")
                .filtered(lambda move: move.is_sale_document())
                .mapped("invoice_line_ids")
            )
            # Get balance from receivable account line - this preserves the sign
            exchange_balance = sum(
                exchange_move.line_ids.filtered(lambda l: l.account_id == rec_account).mapped("balance")
            )
            invoice_line_vals += self._prepare_invoice_lines_by_taxes(invoice_lines, account, exchange_balance)

        invoice_vals = {
            "move_type": "out_invoice",
            "currency_id": company.currency_id.id,
            "partner_id": partner.id,
            "user_id": partner.user_id.id or False,
            "company_id": company.id,
            "journal_id": journal.id,
            "invoice_origin": "Ajuste por diferencia de cambio",
            "invoice_payment_term_id": False,
            "invoice_line_ids": invoice_line_vals,
        }

        if self.wizard_id.fiscal_position == "manual":
            if self.wizard_id.fiscal_position_id:
                invoice_vals["fiscal_position_id"] = self.wizard_id.fiscal_position_id.id
            else:
                invoice_vals["fiscal_position_id"] = False

        # hack para evitar modulo glue con l10n_latam_document
        # hasta el momento tenemos feedback de dos clientes uruguayos de que los ajustes por intereses
        # se hacen comoo factura normal y no ND. Si eventualmente otros clintes solicitan ND tendremos
        # que analizar hacerlo parametrizable y además cambios en validación electrónica con DGI
        # # porque actualmente exige vincular una factura original (implementar poder pasar indicadores globales)
        if (
            journal.country_code != "UY"
            and journal._fields.get("l10n_latam_use_documents")
            and journal.l10n_latam_use_documents
        ):
            debit_note = self.env["account.move"].new(
                {
                    "move_type": "out_invoice",
                    "journal_id": journal.id,
                    "partner_id": partner.id,
                    "company_id": company.id,
                }
            )
            document_types = debit_note.l10n_latam_available_document_type_ids.filtered(
                lambda x: x.internal_type == "debit_note"
            )
            invoice_vals["l10n_latam_document_type_id"] = (
                document_types and document_types[0]._origin.id or debit_note.l10n_latam_document_type_id.id
            )

        return invoice_vals

    def _compute_show_warning(self):
        move_line_ids = self.env.context.get("move_line_ids", [])
        ams_all = self.env["account.move.line"].browse(move_line_ids)
        for line in self:
            ams = ams_all.filtered(lambda m: m.partner_id == line.partner_id).mapped("move_id")
            if all(bool(m.reversed_entry_id) for m in ams):
                line.show_warning = _(
                    '<i class="fa fa-exclamation-triangle text-warning" title="All selected entries for this partner are reversals"></i>'
                )
            elif line.balance == 0.0:
                line.show_warning = _(
                    '<i class="fa fa-exclamation-triangle text-warning" title="The balance for this partner is zero, so no debit/credit note will be created."></i>'
                )
            else:
                line.show_warning = ""
