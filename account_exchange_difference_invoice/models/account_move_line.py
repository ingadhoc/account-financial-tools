from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    exchange_info = fields.Char(compute="_compute_exchange_info")

    def _compute_account_id(self):
        term_lines = self.env["account.move.line"]
        if self._context.get("exchange_diff_account_receivable_id"):
            term_lines = self.filtered(lambda line: line.display_type == "payment_term")
            term_lines.account_id = self._context.get("exchange_diff_account_receivable_id")
        super(AccountMoveLine, self - term_lines)._compute_account_id()

    def _compute_exchange_info(self):
        for rec in self:
            rec.exchange_info = ""
            partial_reconciles = self.env["account.partial.reconcile"].search(
                [("exchange_move_id.id", "=", rec.move_id.id)]
            )
            if partial_reconciles:
                exchange_info = (
                    (partial_reconciles.mapped("debit_move_id") + partial_reconciles.mapped("credit_move_id"))
                    .filtered(lambda l: l.move_type != "entry")
                    .mapped("move_name")
                )
                rec.exchange_info = f"Exchange diff for: {', '.join(exchange_info)}"

                if rec.move_id.exchange_reversal_id:
                    if rec.move_id.exchange_reversal_id.exchange_reversal_id:
                        rec.exchange_info += " (Debit Note Issued)"
                    else:
                        rec.exchange_info += f" (Reversed by: {rec.move_id.exchange_reversal_id.name})"
                else:
                    rec.exchange_info += " (Debit Note Pending)"

            if rec.move_id in rec.move_id.exchange_reversed_move_ids:
                rec.exchange_info += f"Reverses: {', '.join(rec.move_id.exchange_reversed_move_ids.mapped('name'))}"

    def _compute_totals(self):
        exchange_invoices = self.filtered(lambda x: x.product_id == self.env.company.exchange_difference_product)
        normal_lines = self - exchange_invoices

        if exchange_invoices:
            super(AccountMoveLine, exchange_invoices.with_context(force_price_include=True))._compute_totals()

        if normal_lines:
            super(AccountMoveLine, normal_lines)._compute_totals()

    def _get_exchange_difference_domain(self):
        """Lo que queremos mostrar es:
        * todo lo que está en diarios de diferencia de cambio de la compañía actual y que:
            * se haya "convertido" a nc/nd"
            * o que no esté conciliado contra otro asiento de diferencia de cambio
        Basicamente, excluimos todos los asientos de diferencia de cambio que no hayan sido convertidos a nc/nd
        y que no se hayan revertido (es para minimizar ver asientos que odoo genera al conciliar y re-conciliar deuda)
        """
        exchange_journal = self.env.company.currency_exchange_journal_id

        common_domain = [
            ("move_type", "=", "entry"),
            ("journal_id", "=", exchange_journal.id),
            ("account_type", "=", "asset_receivable"),
            ("move_id.exchange_reversed_move_ids", "=", False),
        ]

        # por ahora estamos borrando las reversiones puras de asientos de dif de cambio (Ver account.partial.reconcile)
        # con ese cambio nos evitamos tener que hacer este filtro complejo
        # exchange_domain = [
        #     "|",
        #     "|",
        #     "&",
        #     ("move_id.reversal_move_ids", "!=", False),
        #     ("move_id.exchange_reversal_id", "!=", False),
        #     "&",
        #     ("move_id.reversal_move_ids", "=", False),
        #     ("move_id.reversed_entry_id.exchange_reversal_id", "!=", False),
        #     "&",
        #     ("move_id.reversal_move_ids", "=", False),
        #     ("move_id.reversed_entry_id", "=", False),
        # ]
        # return expression.AND([common_domain, exchange_domain])

        return common_domain

    def action_exchange_difference(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move.line",
            "view_mode": "list",
            "name": "Exchange entries",
            "views": [(self.env.ref("account_exchange_difference_invoice.view_invoice_exchange_list").id, "list")],
            "domain": self._get_exchange_difference_domain(),
            "context": {
                "search_default_to_process": 1,
                "search_default_current_month": 1,
                "group_by": ["partner_id"],
            },
        }

    def action_open_exchange_difference_wizard(self):
        """Server action to open the Exchange Difference Wizard."""
        move_line_ids = self.env.context.get("active_ids", [])
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.exchange.difference.wizard",
            "view_mode": "form",
            "target": "new",
            "name": "Convert to Debit Note",
            "context": {
                "move_line_ids": move_line_ids,
            },
        }
