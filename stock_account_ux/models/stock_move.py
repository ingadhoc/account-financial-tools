from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # ``account_move_id`` (Many2one stored) ya existe en stock_account: guarda el
    # asiento de valorización perpetua y, vía la override de res.company, el de
    # cierre periódico. No lo tocamos. Sumamos un campo navegable que apunta al
    # asiento que valora el movimiento, para llegar a él con un clic desde el
    # reporte de movimientos de productos.
    related_account_move_id = fields.Many2one(
        comodel_name="account.move",
        compute="_compute_related_account_move_id",
        search="_search_related_account_move_id",
        string="Journal Entry",
    )
    # Movimientos cuya valorización ya quedó contabilizada en la v18 (el asiento
    # se reenganchó a ``account_move_id`` en el post-migration 18->19). Como el
    # gasto ya se reconoció en la versión anterior, al facturar en v19 no
    # corresponde volver a generar el COGS anglosajón para ellos. Ver la override
    # de ``_stock_account_prepare_realtime_out_lines_vals`` en account_move.py.
    stock_valuation_migrated = fields.Boolean(
        string="Valuation Booked in v18",
        default=False,
        copy=False,
    )

    @api.depends("account_move_id", "picking_id", "state", "product_id.valuation")
    def _compute_related_account_move_id(self):
        for move in self:
            # Asiento de valorización propio del movimiento (perpetuo) o asiento
            # de cierre asociado (periódico), ambos en ``account_move_id``.
            entries = move.account_move_id
            # La factura relacionada sólo refleja la valorización de ESTE
            # movimiento cuando el producto se valoriza de forma perpetua (al
            # facturar). Con valorización periódica (al cierre) el costo no se
            # registra en la factura sino en el asiento global de cierre, así que
            # no corresponde mostrar la factura como asiento relacionado hasta
            # que ese asiento global se genere.
            if move.product_id.valuation == "real_time":
                entries |= move._get_related_invoices()
            # El campo es Many2one: tomamos el primer asiento disponible. La unión
            # preserva el orden, así que prioriza el de valorización (``account_move_id``)
            # y, si no hay, cae en la primera factura relacionada.
            move.related_account_move_id = entries[:1]

    def _set_value(self, correction_quantity=None):
        """No revalorizar al facturar los movimientos ya valorizados en la v18.

        De fábrica ``account.move._post`` llama ``_set_value`` sobre los
        movimientos de entrada/dropship de la factura para recomputar su
        ``value`` (y de ahí el ``standard_price`` del producto) a partir del
        precio facturado. Para un movimiento migrado ese valor ya viene de la
        v18 (lo backfilleó el post-migration), así que recomputarlo lo pisaría
        con una base distinta. Sólo lo salteamos en el flujo de posteo de la
        factura, que marca el contexto ``skip_migrated_stock_revaluation``; el
        resto de los llamados a ``_set_value`` quedan intactos. Ver tarea 70174.
        """
        moves = self
        if self.env.context.get("skip_migrated_stock_revaluation"):
            moves = self.filtered(lambda m: not (m.stock_valuation_migrated and (m.is_in or m.is_dropship)))
        return super(StockMove, moves)._set_value(correction_quantity=correction_quantity)

    def _get_migrated_valuation_counterpart_account(self):
        """Cuenta de contrapartida del asiento de valorización que la v18 dejó
        reenganchado en ``account_move_id`` (post-migration 18->19).

        En ese asiento el ingreso se contabilizó como alta de activo: débito a
        la cuenta de valorización de stock (Existencias) contra esta
        contrapartida (típicamente una cuenta de compra de mercadería). Es la
        cuenta a la que debe imputarse la línea de factura en v19 para no
        volver a debitar Existencias. Devuelve un recordset vacío si no hay
        asiento o no se puede determinar la contrapartida.
        """
        self.ensure_one()
        entry = self.account_move_id
        if not entry:
            return self.env["account.account"]
        accounts = self.product_id.product_tmpl_id.with_company(self.company_id).get_product_accounts()
        valuation_account = accounts.get("stock_valuation")
        counterpart = entry.line_ids.filtered(lambda line: line.account_id and line.account_id != valuation_account)
        return counterpart[:1].account_id

    def _search_related_account_move_id(self, operator, value):
        """El campo es calculado y no se almacena (las facturas relacionadas se
        resuelven al vuelo), por lo que necesitamos un search method para poder
        filtrar por el asiento contable en los reportes de movimientos.

        Un movimiento sólo puede tener asiento relacionado si tiene su propio
        asiento de valorización (``account_move_id``) o un albarán
        (``picking_id``, del que cuelgan las facturas relacionadas), así que
        acotamos los candidatos a ese subconjunto antes de evaluar el campo
        calculado.

        Ojo: el motor de dominios de Odoo normaliza ``=``/``!=`` a ``in``/``not in``
        y el ``False`` llega como una colección (``[False]``), así que normalizamos
        operador y valor antes de decidir."""
        candidates = self.search(["|", ("account_move_id", "!=", False), ("picking_id", "!=", False)])
        # Normalizar el valor a lista (puede venir como False, escalar, lista u OrderedSet).
        if isinstance(value, str) or not hasattr(value, "__iter__"):
            values = [value]
        else:
            values = list(value)
        # Filtro "establecido / no establecido": el valor es sólo False/vacío.
        if operator in ("=", "!=", "in", "not in") and all(not v for v in values):
            with_entry = candidates.filtered("related_account_move_id")
            # ``=``/``in`` contra [False] => SIN asiento; ``!=``/``not in`` => CON asiento.
            want_without = operator in ("=", "in")
            if want_without:
                return [("id", "not in", with_entry.ids)]
            return [("id", "in", with_entry.ids)]
        # Filtro por un asiento concreto (por id o por nombre del asiento).
        field = "display_name" if any(isinstance(v, str) for v in values) else "id"
        moves = self.env["account.move"].search([(field, operator, value)])
        matched = candidates.filtered(lambda m: m.related_account_move_id & moves)
        return [("id", "in", matched.ids)]
