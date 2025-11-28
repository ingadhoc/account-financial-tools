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
            move._reconcile_reversed_moves(reverse_moves, move_reverse_cancel=False)
        return res
