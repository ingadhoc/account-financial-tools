from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _compute_account_id(self):
        """Imputar la línea de factura de compra de un movimiento migrado de la
        v18 a la contrapartida de su asiento de valorización, en vez de a la
        cuenta de valorización de stock.

        De fábrica (``stock_account``) este compute pisa la cuenta de la línea
        con ``accounts['stock_valuation']`` (Existencias) para productos
        ``real_time``, contabilizando el alta del activo en la propia factura.
        Para un movimiento cuya valorización YA quedó registrada en la v18
        (``stock_valuation_migrated``) eso vuelve a dar de alta el activo: el
        stock ya está valorizado. En su lugar tomamos la contrapartida del
        asiento migrado (el crédito de aquel alta), que es la cuenta que la
        factura de proveedor debe cancelar. Ver tarea 70174.
        """
        super()._compute_account_id()
        for line in self:
            move = line.move_id
            if not move.is_purchase_document() or line.display_type == "cogs":
                continue
            if not line._eligible_for_stock_account() or line.product_id.valuation != "real_time":
                continue
            stock_moves = line._get_stock_moves()
            if not stock_moves or not all(m.stock_valuation_migrated for m in stock_moves):
                continue
            counterpart_account = stock_moves[:1]._get_migrated_valuation_counterpart_account()
            if counterpart_account:
                line.account_id = counterpart_account
