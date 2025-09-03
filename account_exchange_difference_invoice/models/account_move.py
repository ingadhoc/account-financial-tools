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

    def action_post(self):
        res = super().action_post()
        for move in self:
            reversed_lines = move.exchange_reversed_move_ids.line_ids
            if not reversed_lines:
                continue

            # probar usar directamente método "_reconcile_reversed_moves"?
            if move.amount_residual > 0:
                target_line = reversed_lines.filtered(lambda l: l.credit > 0)
            elif move.amount_residual < 0:
                target_line = reversed_lines.filtered(lambda l: l.debit > 0)
            else:
                continue

            if target_line:
                move.js_assign_outstanding_line(target_line.id)
        return res
