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
        check on create.
        """
        company = self._get_payment_company(batch_result["lines"])
        if not company:
            return super()._get_batch_available_journals(batch_result)
        journals = self.env["account.journal"].search(
            [
                *self.env["account.journal"]._check_company_domain(company),
                ("type", "in", ("bank", "cash", "credit")),
            ]
        )
        if batch_result["payment_values"]["payment_type"] == "inbound":
            return journals.filtered("inbound_payment_method_line_ids")
        return journals.filtered("outbound_payment_method_line_ids")

    @api.model
    def _get_batch_journal(self, batch_result):
        """Same choice as native, but among the journals of the paying company.

        Journals are ordered by ``branch_order``, so the branch's own ones come first.
        """
        company = self._get_payment_company(batch_result["lines"])
        if not company:
            return super()._get_batch_journal(batch_result)
        payment_values = batch_result["payment_values"]
        currency_domain = [("currency_id", "=", payment_values["currency_id"])]
        partner_bank_domain = [("bank_account_id", "=", payment_values["partner_bank_id"])]
        default_domain = [
            *self.env["account.journal"]._check_company_domain(company),
            ("type", "in", ("bank", "cash", "credit")),
            ("id", "in", self.available_journal_ids.ids),
        ]
        if payment_values["partner_bank_id"]:
            extra_domains = (currency_domain + partner_bank_domain, partner_bank_domain, currency_domain, [])
        else:
            extra_domains = (currency_domain, [])
        for extra_domain in extra_domains:
            if journal := self.env["account.journal"].search(default_domain + extra_domain, limit=1):
                return journal
        return self.env["account.journal"]
