##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    @api.constrains("payment_account_id", "journal_id")
    def _check_outstanding_account_not_suspense(self):
        """La cuenta de pagos/cobros pendientes (outstanding) no puede coincidir con la
        cuenta transitoria (suspense) del diario.

        Es el mismo problema que ``account.journal._check_suspense_account_not_outstanding``,
        pero disparado desde el otro lado: al editar la cuenta outstanding del método de
        pago. Si coincide con la transitoria del diario, la conciliación bancaria nunca
        se puede validar (el botón "Validar" queda gris).
        """
        for line in self:
            suspense = line.journal_id.suspense_account_id
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
