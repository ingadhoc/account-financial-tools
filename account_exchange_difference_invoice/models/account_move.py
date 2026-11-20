from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    exchange_reversal_id = fields.Many2one(
        "account.move",
        string="Exchange Reversal Entry",
        help="Asiento con el cual se revirtió el ajuste por diferencia de cambio para generar la Factura",
        copy=False,
        store=True,
    )
    exchange_reversed_move_ids = fields.One2many(
        "account.move",
        "exchange_reversal_id",
        string="Exchange Entries",
        help="Asientos revertidos con este asiento para generar la factura de diferencia de cambio",
    )

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        # EXTENDS 'account'
        results = super()._prepare_product_base_line_for_taxes_computation(product_line)
        exchange_invoice = self.filtered(
            lambda x: x.line_ids.mapped("product_id")
            and self.env.company.exchange_difference_product.id in x.line_ids.mapped("product_id").ids
        )
        if exchange_invoice:
            results["special_mode"] = "total_included"
        return results

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for move in self:
            reverse_moves = move.exchange_reversed_move_ids
            if not reverse_moves:
                continue

            reverse_moves.exchange_reversed_move_ids.write({"ref": move.name})
            move._reconcile_exchange_reversed_move(reverse_moves[:1])
        return res

    def _reconcile_exchange_reversed_move(self, reverse_move):
        # Replaces account.move._reconcile_reversed_moves, removed in 20.0, keeping its pairing and conditions
        self.ensure_one()
        groups = (
            (self.line_ids + reverse_move.line_ids)
            .filtered(lambda line: not line.reconciled)
            .sorted(lambda line: line.account_type not in ("asset_receivable", "liability_payable"))
            .grouped(lambda line: (line.account_id, line.currency_id))
        )
        for (account, _currency), lines in groups.items():
            if (
                all(not line.reconciled for line in lines)
                and account.reconcile
                or account.account_type in ("asset_cash", "liability_credit_card")
            ):
                lines.with_context(move_reverse_cancel=False).reconcile()
