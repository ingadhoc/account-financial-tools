##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def action_undo_reconciliation(self):
        ''' Los statement lines que fueron creados en versiones < 15.0 no tienen un accounnt.move.line asociado, para
        que el circuito completo de desconciliacion y conciliacion puedan funcionar debemos corregir esto creando
        manualmente un asiento similar al que se genera automaticamente. Tambien, las bases que fueron migrades tienen
        el problema donde reconocen que los statement.lines tienen si tiene un aml, pero este es el del pago y al
        desconciliar modifica el asiento del pago dejandolo incorrecto. En este metodo:
        1. Identificamos los st.lines que tengan am que sean pago y los corregimos
        2. creamos un nuevo asiento similar al que se genera automatico al crear el st.line.
        3, desvinculamos el am del pago del st.line '''
        invoice_names = self.line_ids.filtered(lambda x: x.account_type in ['asset_receivable', 'liability_payable']).mapped('name')
        if len(invoice_names)==1:
            body = 'La factura {} dejó de figurar como pagada.'.format(invoice_names[0])
            self.move_id.message_post(body=body)
        if len(invoice_names)>1:
            invoice_names_formatted = ", ".join(invoice_names)
            body = 'Las facturas {} dejaron de figurar como pagadas.'.format(invoice_names_formatted)
            self.move_id.message_post(body=body)
        super().action_undo_reconciliation()

