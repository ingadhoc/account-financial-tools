##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_undo_reconciliation(self):
        """Los statement lines que fueron creados en versiones < 15.0 no tienen un account.move.line asociado, para
        que el circuito completo de desconciliacion y conciliacion puedan funcionar debemos corregir esto creando
        manualmente un asiento similar al que se genera automaticamente. Tambien, las bases que fueron migrades tienen
        el problema donde reconocen que los statement.lines tienen si tiene un aml, pero este es el del pago y al
        desconciliar modifica el asiento del pago dejandolo incorrecto. En este metodo:
        1. Identificamos los st.lines que tengan am que sean pago y los corregimos
        2. creamos un nuevo asiento similar al que se genera automatico al crear el st.line.
        3, desvinculamos el am del pago del st.line"""
        # arreglamos solo los que son una transferencia interna o si hay una linea a cobrar / a pagar porque en 13, cuando conciliabamos contra gasto se generaba un pago
        # pero en este caso odoo ya lo resuelve bien. Si este filtro no llega a ir bien por algo podriamos ver si tiene payment_group_id (pero no es lo mas elegante porque podria
        # haber clientes sin payment_group) o si el payment tiene partner_id
        st_lines_to_fix = self.filtered(
            lambda x: x.move_id.payment_ids.is_internal_transfer
            or (
                x.move_id.payment_ids
                and x.move_id.line_ids.filtered(
                    lambda x: x.account_id.account_type in ("asset_receivable", "liability_payable")
                )
            )
        )
        to_post = self.browse()

        for st_line in st_lines_to_fix:
            payments = st_line.move_id.payment_ids
            liquidity_lines, counterpart_lines, writeoff_lines = payments._seek_for_lines()
            # si la cuenta de mi diario es la misma que la cuenta de la linea de liqudiez, es un pago
            # migrado y tenemos que cambiar por la cuenta outstanding
            if payments.journal_id.default_account_id != liquidity_lines.account_id:
                continue
            # Creamos la nueva linea manual como si se hubiese creado en 15 desde 0. y la vinculamos al statement line
            # de esta maera desviculamos el asiento del pago
            st_line_new = self.new(
                {
                    "statement_id": st_line.statement_id,
                    "date": st_line.date,
                    "amount": st_line.amount,
                    "journal_id": st_line.journal_id,
                    "move_type": st_line.move_type,
                    "partner_id": st_line.partner_id,
                    "payment_ref": st_line.payment_ref,
                }
            )
            move_vals = st_line_new.move_id._convert_to_write(st_line_new._cache)

            st_line.with_context(skip_account_move_synchronization=True).write(
                {"move_id": self.env["account.move"].create(move_vals)}
            )
            to_post += st_line

            # Corregimos el asiento del pago para que en lugar de ser AR/AP vs liquidez, sea AR/AP vs outstanding
            payments._compute_outstanding_account_id()
            outstanding_account = payments.outstanding_account_id
            # Hicimos esto para desvincular el pago del extracto y de la línea del extracto que se está desconciliando
            payments.statement_line_id = False
            # Al pago le cambiamos la cuenta de outstanding en lugar de la cuenta de liquidez
            payments.move_id.line_ids.filtered(
                lambda x: x.account_id == liquidity_lines.account_id
            ).account_id = outstanding_account.id
            # liquidity_lines.account_id = outstanding_account.id

        super().action_undo_reconciliation()
        to_post.mapped("move_id").action_post()
        # publicamos los asientos de las líneas del extracto contable
        # for st_line in st_lines_to_fix:
        #    st_line.move_id._post(soft=False)
