from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def action_close_stock_valuation(self, at_date=None, auto_post=False):
        """Al generar el asiento global de cierre de valorización periódica,
        vincularlo a los ``stock.move`` que valoriza (campo ``account_move_id``),
        igual que los movimientos perpetuos quedan ligados a su asiento.

        De fábrica el asiento de cierre se arma agregado por cuenta contable y
        no queda asociado a ningún movimiento, por lo que en los reportes de
        movimientos de productos no había forma de llegar al asiento que los
        valoró. Guardamos el cierre en el ``account_move_id`` estándar (stored)
        para que el campo navegable ``related_account_move_id`` (computado), los filtros
        "Con/Sin Asiento" y el buscador funcionen igual que con la valorización
        perpetua, sin distinguir perpetuo vs. periódico."""
        self.ensure_one()
        # El corte anterior hay que leerlo ANTES de super(): super() registra
        # este cierre y _get_last_closing_date pasaría a devolver el nuevo.
        previous_closing_date = self._get_last_closing_date()
        action = super().action_close_stock_valuation(at_date=at_date, auto_post=auto_post)
        closing_move = self.env["account.move"]
        if isinstance(action, dict) and action.get("res_model") == "account.move":
            closing_move = self.env["account.move"].browse(action.get("res_id")).exists()
        if not closing_move:
            return action
        moves = self._get_periodic_closing_stock_moves(at_date, previous_closing_date)
        # No tocar movimientos que ya tienen un asiento posteado (perpetuos o un
        # cierre previo válido); sí re-vincular si el asiento anterior quedó sin
        # postear (p. ej. un cierre cancelado y regenerado).
        moves = moves.filtered(lambda m: not m.account_move_id or m.account_move_id.state != "posted")
        if moves:
            moves.account_move_id = closing_move.id
        return action

    def _get_periodic_closing_stock_moves(self, at_date=None, from_date=None):
        """Movimientos de productos con valorización periódica cubiertos por el
        asiento de cierre, replicando el alcance de
        ``_get_location_valuation_vals``: productos periódicos, dentro del rango
        de fechas del cierre, que entran o salen de ubicaciones valuadas."""
        self.ensure_one()
        if isinstance(at_date, str):
            at_date = fields.Date.from_string(at_date)
        valued_locations = self.env["stock.location"].search(
            [
                ("company_id", "in", [self.id, False]),
            ]
        )
        if not valued_locations:
            return self.env["stock.move"]
        domain = [
            "|",
            "&",
            ("is_out", "=", True),
            ("location_dest_id", "in", valued_locations.ids),
            "&",
            ("is_in", "=", True),
            ("location_id", "in", valued_locations.ids),
            ("product_id.is_storable", "=", True),
            ("company_id", "=", self.id),
            ("related_account_move_id", "=", False),
        ]
        if from_date:
            domain.append(("date", ">=", from_date))
        if at_date:
            domain.append(("date", "<=", at_date))
        return self.env["stock.move"].search(domain)
