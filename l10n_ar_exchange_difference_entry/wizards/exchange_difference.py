from odoo import api, fields, models


class ExchangeDifferenceWizard(models.TransientModel):
    _name = "l10n_ar.exchange.difference.wizard"
    _description = "Exchange Difference Wizard"

    move_ids = fields.Many2many("account.move")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if "default_move_ids" in self.env.context:
            res["move_ids"] = self.env.context["default_move_ids"]
        return res

    def action_create_debit_credit_note(self):
        self.move_ids.line_ids.remove_move_reconcile()
        exchange_product = self.env.company.exchange_difference_product
        for rec in self.move_ids:
            partial_reconcile = self.env["account.partial.reconcile"].search([("exchange_move_id.id", "=", rec.id)])
            original_invoice = partial_reconcile.debit_move_id.move_id
            letter = original_invoice.l10n_latam_document_type_id.l10n_ar_letter

            if letter == "A":
                doc_type = self.env.ref("l10n_ar.dc_a_nd")
            elif letter == "B":
                doc_type = self.env.ref("l10n_ar.dc_b_nd")
            elif letter == "C":
                doc_type = self.env.ref("l10n_ar.dc_c_nd")

            sale_line = rec.line_ids.filtered(lambda x: x.account_type == "asset_receivable")
            amount = sale_line.debit

            rec.write(
                {
                    "name": False,
                    "state": "draft",
                    "partner_id": original_invoice.partner_id.id,
                    "move_type": "out_invoice",
                    "l10n_latam_document_type_id": doc_type.id,
                    # "fiscal_position_id": False,
                }
            )

            # Por ahora el prodcto de diferencia de cambio tiene solo el 21%
            exch_tax = exchange_product.taxes_id

            rec.line_ids.create(
                {
                    "move_id": rec.id,
                    "product_id": exchange_product.id,
                    "account_id": self.env.company.income_currency_exchange_account_id.id,
                    "tax_ids": [(6, 0, exch_tax.ids)],
                    "price_unit": amount / (1 + exch_tax.amount / 100),
                }
            )

            # Keep only the exchange difference product line
            extra_invoice_lines = rec.invoice_line_ids.filtered(lambda x: x.product_id != exchange_product)

            new_sale_line = rec.line_ids.filtered(
                lambda x: x.account_type == "asset_receivable" and x not in extra_invoice_lines
            )
            extra_invoice_lines.unlink()

            # If account has a currency, zero out the amount in currency
            account_currency = new_sale_line.account_id.currency_id
            if account_currency:
                new_sale_line.write(
                    {
                        "currency_id": account_currency.id,
                        "amount_currency": 0.0,
                        "debit": amount,
                        "credit": amount,
                    }
                )
            partial_reconcile.write({"exchange_move_id": False})
            rec.action_post()

            rec.write({"payment_state": "not_paid"})
            rec.js_assign_outstanding_line(partial_reconcile.credit_move_id.id)
            rec.write({"payment_state": "paid"})
