##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    shared_to_branches = fields.Boolean(
        related="journal_id.shared_to_branches",
        store=True,
    )

    @api.constrains("payment_account_id", "journal_id")
    def _check_outstanding_account_not_suspense(self):
        """La cuenta de pagos/cobros pendientes (outstanding) no puede coincidir con la
        cuenta transitoria (suspense) del diario.

        Es el mismo problema que ``account.journal._check_suspense_account_not_outstanding``,
        pero disparado desde el otro lado: al editar la cuenta outstanding del método de
        pago. Si coincide con la transitoria del diario, la conciliación bancaria nunca
        se puede validar (el botón "Validar" queda gris).

        Igual que la del diario, se puede saltear con ``skip_suspense_outstanding_check``
        en el contexto, para el módulo que crea el diario y sus cuentas en varios pasos
        dentro de una misma transacción.
        """
        if self.env.context.get("skip_suspense_outstanding_check"):
            return
        for line in self:
            journal = line.journal_id
            if not journal:
                continue
            suspense = journal.suspense_account_id
            if line.payment_account_id and suspense and line.payment_account_id == suspense:
                raise ValidationError(
                    _(
                        "La cuenta de pagos/cobros pendientes (%(account)s) no puede ser la misma que la "
                        "cuenta transitoria del diario «%(journal)s». Si lo son, no vas a poder validar las "
                        "conciliaciones bancarias.",
                        account=line.payment_account_id.display_name,
                        journal=line.journal_id.display_name,
                    )
                )
