from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """Al postear una factura, ``stock_account._post`` revaloriza los
        movimientos de entrada/dropship (``stock.move._set_value``) contra el
        precio facturado. Marcamos el contexto para que la override de
        ``stock.move._set_value`` saltee esa revalorización en los movimientos
        migrados de la v18, cuyo valor ya está contabilizado. Ver tarea 70174.
        """
        return super(AccountMove, self.with_context(skip_migrated_stock_revaluation=True))._post(soft=soft)

    def _stock_account_prepare_realtime_out_lines_vals(self):
        """Evitar la doble contabilización al facturar en v19 movimientos que ya
        se valorizaron en la v18.

        De fábrica, al postear la factura se generan los apuntes de COGS
        anglosajón por cada línea de producto ``real_time`` (ver
        ``stock_account`` ``account.move._post`` -> este método). Ese cálculo
        parte de las líneas de factura y NO consulta ``stock.move.account_move_id``,
        así que no sabe que el movimiento entregado en la v18 ya tiene su asiento
        de valorización (reenganchado en el post-migration 18->19). Sin este
        filtro, el gasto se reconocería dos veces: una en la v18 y otra en el
        COGS de la factura v19.

        Podamos únicamente las líneas cuyos movimientos de stock están TODOS
        marcados como ``stock_valuation_migrated``; los albaranes normales de v19
        siguen generando su COGS con normalidad.
        """
        vals_list = super()._stock_account_prepare_realtime_out_lines_vals()
        if not vals_list:
            return vals_list
        skip_line_ids = set()
        for move in self:
            for line in move.invoice_line_ids:
                stock_moves = line._get_stock_moves()
                if stock_moves and all(m.stock_valuation_migrated for m in stock_moves):
                    skip_line_ids.add(line.id)
        if not skip_line_ids:
            return vals_list
        return [vals for vals in vals_list if vals.get("cogs_origin_id") not in skip_line_ids]
