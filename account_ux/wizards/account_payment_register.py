from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.model
    def _get_payment_company(self, lines):
        """The active company when the whole debt is its legal entity, else an empty recordset.

        Native reads the company out of the debt and never looks at where the user is: the
        shallowest company of the lines, or the root one when the lines come from sibling
        companies (``account/wizard/account_payment_register.py``). Standing on a branch and
        paying an invoice of its own legal entity, that hands the payment to the parent — which
        is not who is paying. If any company of the debt is another legal entity —sibling
        branches with different Tax IDs, where the accounts are not compatible either— the
        company of the debt travels, exactly as native does.
        """
        companies = lines.company_id
        legal_entity = self.env.company._get_legal_entity_companies()
        if companies and all(company in legal_entity for company in companies):
            return self.env.company
        return self.env["res.company"]

    def _get_wizard_values_from_batch(self, batch_result):
        """Book the payment in the company the user is standing on when it can be theirs.

        The field stays readonly; choosing it by hand is what the receipt flow is for.
        """
        values = super()._get_wizard_values_from_batch(batch_result)
        if company := self._get_payment_company(batch_result["lines"]):
            values["company_id"] = company.id
        return values

    @api.model
    def _get_batch_available_journals(self, batch_result):
        """Offer the journals the paying company can use, not the ones of the debt.

        Native searches them with the company of the debt, so a payment moved to the branch
        was offered the parent's journals, and one not shared to the branch failed the company
        check on create. The company travels in the context, so the overrides of other modules
        (e.g. ``account_journal_security``) still apply.
        """
        return super(AccountPaymentRegister, self._with_payment_company(batch_result))._get_batch_available_journals(
            batch_result
        )

    @api.model
    def _get_batch_journal(self, batch_result):
        """Same choice as native, but among the journals of the paying company.

        Journals are ordered by ``branch_order``, so the branch's own ones come first.
        """
        return super(AccountPaymentRegister, self._with_payment_company(batch_result))._get_batch_journal(batch_result)

    @api.model
    def _with_payment_company(self, batch_result):
        """Make ``account.journal._check_company_domain`` use the paying company, if any."""
        if company := self._get_payment_company(batch_result["lines"]):
            return self.with_context(account_ux_payment_company_id=company.id)
        return self
