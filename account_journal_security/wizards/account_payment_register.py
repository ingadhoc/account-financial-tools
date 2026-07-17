from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _get_batch_available_journals(self, batch_result):
        # `journal_id` es un campo stored con compute_sudo=True (default de Odoo para
        # computed stored). Cuando el ORM lo precomputa eleva el recordset a sudo y este
        # search de diarios corre en sudo, bypaseando las ir.rules de journal_security.
        # Como resultado, diarios total-restringidos a otros usuarios se cuelan en
        # available_journal_ids y disparan un AccessError al renderizarse el pago masivo.
        # Apagamos el sudo (env.uid ya es el usuario real) para que las reglas apliquen,
        # y activamos journal_security para filtrar tambien los diarios de solo lectura.
        wizard = self.sudo(False).with_context(journal_security=True)
        return super(AccountPaymentRegister, wizard)._get_batch_available_journals(batch_result)
