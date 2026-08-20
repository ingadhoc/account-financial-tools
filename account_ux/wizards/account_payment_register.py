##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _get_wizard_values_from_batch(self, batch_result):
        """Book the payment in the company the user is standing on when it can be theirs.

        Native reads the company out of the debt and never looks at where the user is:
        the shallowest company of the lines, or the root one when the lines come from
        sibling companies (``account/wizard/account_payment_register.py``). Standing on a
        branch and paying an invoice of its own legal entity, that hands the payment to
        the parent — which is not who is paying.

        The single criterion decides it, so this adds no rule of its own: if every company
        of the debt is the same legal entity as the active one, the payment is that
        company's and it keeps it. If any of them is not —sibling branches with different
        Tax IDs, where the accounts are not compatible either— the company of the debt
        travels, exactly as native does. The field stays readonly in both cases; choosing
        it by hand is what the receipt flow is for.
        """
        values = super()._get_wizard_values_from_batch(batch_result)

        companies = batch_result["lines"].company_id
        legal_entity = self.env.company._get_legal_entity_companies()
        if companies and all(company in legal_entity for company in companies):
            values["company_id"] = self.env.company.id
        return values
