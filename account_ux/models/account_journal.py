##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    mail_template_id = fields.Many2one(
        "mail.template",
        "Email Template",
        domain=[("model", "=", "account.move")],
        help="If set an email will be sent to the customer after the invoices"
        " related to this journal has been validated.",
    )

    @api.constrains("currency_id")
    def check_currency(self):
        for rec in self.filtered(lambda x: x.currency_id == x.company_id.currency_id):
            raise ValidationError(
                _(
                    "Solo puede utilizar una moneda secundaria distinta a la " "moneda de la compañía (%s).",
                    rec.company_id.currency_id.name,
                )
            )

    @api.constrains(
        "suspense_account_id",
        "inbound_payment_method_line_ids",
        "outbound_payment_method_line_ids",
    )
    def _check_suspense_account_not_outstanding(self):
        """La cuenta transitoria (suspense) del diario no puede coincidir con una
        cuenta de pagos/cobros pendientes (outstanding).

        Si coinciden, el widget de conciliación bancaria nunca habilita "Validar":
        ``bank.rec.widget._compute_state`` deja ``state='invalid'`` mientras la cuenta
        transitoria siga presente en las líneas, y al conciliar contra un pago cuya
        contrapartida está en esa misma cuenta, la transitoria nunca sale. El botón
        queda gris sin mensaje que lo explique. Bloqueamos la configuración de raíz.

        Se puede saltear pasando ``skip_suspense_outstanding_check`` en el contexto. Es
        para el módulo que crea un diario en su instalación y arma sus cuentas en varios
        pasos dentro de la misma transacción: ahí un estado intermedio puede coincidir y
        haría fallar el install entero, mientras que la configuración final es válida. La
        edición manual del diario nunca lleva ese contexto, así que sigue validada.
        """
        if self.env.context.get("skip_suspense_outstanding_check"):
            return
        for journal in self:
            suspense = journal.suspense_account_id
            if not suspense:
                continue
            outstanding_accounts = (
                journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids
            ).payment_account_id
            if suspense in outstanding_accounts:
                raise ValidationError(
                    _(
                        "En el diario «%(journal)s» la cuenta transitoria (%(account)s) no puede ser la "
                        "misma que una cuenta de pagos/cobros pendientes (outstanding). Si lo son, no vas a "
                        "poder validar las conciliaciones bancarias contra esos pagos. Configurá cuentas distintas.",
                        journal=journal.display_name,
                        account=suspense.display_name,
                    )
                )

    def write(self, vals):
        """We need to allow to change to False the value for restricted for hash for the journal when this value is setted."""
        if "restrict_mode_hash_table" in vals and not vals.get("restrict_mode_hash_table"):
            restrict_mode_hash_table = vals.get("restrict_mode_hash_table")
            vals.pop("restrict_mode_hash_table")
            res = super().write(vals)
            self._write({"restrict_mode_hash_table": restrict_mode_hash_table})
            return res
        return super().write(vals)

    @api.depends("type")
    def _compute_payment_sequence(self):
        # Por defecto lo ponemos en False para evitar errores en la secuencia
        super()._compute_payment_sequence()
        for journal in self:
            journal.payment_sequence = False

    @api.model
    def _fill_missing_values(self, vals, protected_codes=False):
        journal_type = vals.get("type")
        company = self.env["res.company"].browse(vals["company_id"]) if vals.get("company_id") else self.env.company
        if journal_type == "credit":
            if not vals.get("default_account_id"):
                default_account_id = self._create_default_account(company, journal_type, vals)
                vals["default_account_id"] = default_account_id
        super()._fill_missing_values(vals, protected_codes=protected_codes)
