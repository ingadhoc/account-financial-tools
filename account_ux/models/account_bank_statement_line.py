##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    duplicated_group = fields.Char(
        readonly=True,
        help='Technical field used to store information group a possible duplicates bank statement line')

    def button_cancel_reconciliation(self):
        """ Clean move_name to allow reconciling with new line.
        """
        res = super().button_cancel_reconciliation()
        self.write({'move_name': False})
        return res

    # TODO remove in version 15.0 only needed to clean up some statements with move name is set and it should not in
    # order to be able to reconcile the line statement line in future
    def button_fix_clean_move_name(self):
        self.write({'move_name': False})

    def button_undo_reconciliation(self):
        ''' Los statement lines que fueron creados en versiones < 15.0 no tienen un accounnt.move.line asociado, para
        que el circuito completo de desconciliacion y conciliacion puedan funcionar debemos corregir esto creando
        manualmente un asiento similar al que se genera automaticamente. Tambien, las bases que fueron migrades tienen
        el problema donde reconocen que los statement.lines tienen si tiene un aml, pero este es el del pago y al
        desconciliar modifica el asiento del pago dejandolo incorrecto. En este metodo:
        1. Identificamos los st.lines que tengan am que sean pago y los corregimos
        2. creamos un nuevo asiento similar al que se genera automatico al crear el st.line.
        3, desvinculamos el am del pago del st.line '''
        st_lines_to_fix = self.filtered(lambda x: x.move_id.payment_id)
        for st_line in st_lines_to_fix:

            payment = st_line.move_id.payment_id

            # Creamos la nueva linea manual como si se hubiese creado en 15 desde 0. y la vinculamos al statement line
            # de esta maera desviculamos el asiento del pago
            st_line_new = self.new({
                'statement_id': st_line.statement_id,
                'date': st_line.date,
                'extract_state': st_line.extract_state,
                'journal_id': st_line.journal_id,
                'move_id': st_line.move_id,
                'move_type': st_line.move_type,
                'payment_ref': st_line.move_type})
            move_vals = st_line_new.move_id._convert_to_write(st_line_new._cache)

            st_line.with_context(skip_account_move_synchronization=True).write({
                'move_id': self.env['account.move'].create(move_vals)})

            # Corregimos el asiento del pago para que en lugar de ser AR/AP vs liquidez, sea AR/AP vs outstanding
            payment._compute_outstanding_account_id()
            outstanding_account = payment.outstanding_account_id
            # Hicimos esto para desvincular el pago del extracto y de la línea del extracto que se está desconciliando
            payment.statement_line_id = False
            payment.statement_id = False
            # Al pago le cambiamos la cuenta de otstanding en lugar de la cuenta de liquidez
            payment.move_id.line_ids.filtered(lambda x: x.account_internal_type == 'liquidity').account_id = outstanding_account.id

        super().button_undo_reconciliation()
        # publicamos los asientos de las líneas del extracto contable
        for st_line in st_lines_to_fix:
            st_line.move_id._post(soft=False)
