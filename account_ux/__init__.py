##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from . import reports
from . import models
from . import wizards
from .hooks import uninstall_hook
from odoo.fields import Domain
from odoo.addons.account.models.account_payment import AccountPayment
from odoo.addons.account.models.account_move import AccountMove


def _change_receipt_name(env):
    report = env.ref("account.action_report_payment_receipt")
    report.print_report_name = (
        "(object.partner_type == 'supplier' and 'Orden de Pago' or 'Recibo') + ' ' + (object.name or 'Borrador')"
    )


def monkey_patches():
    def _compute_available_journal_ids_patch(self):
        """
        Volvemos a usar _check_company_domain que odoo lo abandonó en 19
        """
        journals = self.env["account.journal"].search(
            Domain(self.env["account.journal"]._check_company_domain(self.company_id))
            & Domain([("type", "in", ("bank", "cash", "credit"))])
        )

        for pay in self:
            if pay.payment_type == "inbound":
                pay.available_journal_ids = journals.filtered("inbound_payment_method_line_ids")
            else:
                pay.available_journal_ids = journals.filtered("outbound_payment_method_line_ids")

    def propagate(method1, method2):
        """Propagate decorators from ``method1`` to ``method2``, and return the
        resulting method.
        """
        if method1:
            for attr in ("_returns",):
                if hasattr(method1, attr) and not hasattr(method2, attr):
                    setattr(method2, attr, getattr(method1, attr))
        return method2

    def _patch_method(cls, name, method):
        """Método para aplicar monkey patches.
        cls --> clase
        name --> nombre del método original
        method --> nombre del método que tiene el parche"""

        origin = getattr(cls, name)
        method.origin = origin
        wrapped = propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    _patch_method(AccountPayment, "_compute_available_journal_ids", _compute_available_journal_ids_patch)
