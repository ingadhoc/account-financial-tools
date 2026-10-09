# © ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestPaymentAvailableJournals(AccountTestInvoicingCommon):
    """El monkey patch de ``_compute_available_journal_ids`` conserva el ``@api.depends`` del core.

    Sin la dependencia, cambiar el tipo de pago no recalculaba los diarios disponibles y un
    diario que solo cobra quedaba elegido en un pago saliente.
    """

    def test_switching_the_payment_type_drops_a_journal_that_cannot_pay(self):
        inbound_only = self.company_data["default_journal_cash"].copy({"name": "Solo cobros", "code": "SCOB"})
        inbound_only.outbound_payment_method_line_ids.unlink()

        with Form(self.env["account.payment"].with_context(default_payment_type="inbound")) as payment:
            payment.journal_id = inbound_only
            payment.payment_type = "outbound"

            self.assertNotIn(inbound_only, payment.available_journal_ids)
            self.assertNotEqual(payment.journal_id, inbound_only)
