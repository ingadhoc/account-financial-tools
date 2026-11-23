##############################################################################
#
#    Copyright (C) 2024  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import _, api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    fci_interest_amount = fields.Monetary(
        string="Accrued Interest Amount",
        default=0.0,
        help="Fixed interest amount to accrue on FCI withdrawal.",
        currency_field="currency_id",
    )

    # Computed helper field used to show/hide the interest field in the view
    is_fci_payment = fields.Boolean(
        string="Is FCI Payment",
        compute="_compute_is_fci_payment",
    )

    @api.depends("destination_journal_id", "destination_journal_id.is_fci_journal")
    def _compute_is_fci_payment(self):
        for payment in self:
            payment.is_fci_payment = payment.journal_id.is_fci_journal

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        """
        Override to inject an interest line when the destination journal is an FCI journal
        and the fci_interest_rate is set.

        Expected journal entry for an FCI withdrawal (outbound transfer to FCI):
          - Bank line (origin):      Credit total amount  (e.g. 1,015,000)
          - FCI line (destination):  Debit  capital amount (amount - interest, e.g. 1,000,000)
          - Interest line:           Credit interest amount using fci_income_account_id (e.g. 15,000)
        """
        self.ensure_one()

        # Build a write-off line for the interest amount when applicable
        extra_write_off = list(write_off_line_vals) if write_off_line_vals else []

        if (
            self.journal_id.is_fci_journal
            and self.payment_type == "outbound"
            and not self.paired_internal_transfer_payment_id
            and self.fci_interest_amount > 0.0
        ):
            interest_amount_currency = -self.fci_interest_amount
            interest_balance = self.currency_id._convert(
                interest_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
            extra_write_off.append(
                {
                    "name": _("FCI Accrued Interest"),
                    "account_id": self.journal_id.fci_income_account_id.id,
                    "partner_id": self.partner_id.id,
                    "currency_id": self.currency_id.id,
                    "amount_currency": interest_amount_currency,
                    "balance": interest_balance,
                }
            )

        return super()._prepare_move_lines_per_type(
            write_off_line_vals=extra_write_off or None,
            force_balance=force_balance,
        )

    def _generate_journal_entry(self, write_off_line_vals=None):
        """
        Override to bypass the automatic reconciliation of the interest line when it's an FCI payment.
        This is needed to keep the interest line open (unreconciled) until the end of the period, when it will be reconciled with a manual journal entry.
        """
        move_vals = super()._generate_journal_entry(write_off_line_vals=write_off_line_vals)

        if self.paired_internal_transfer_payment_id.is_fci_payment:
            # Adjust the payment amount to include the FCI interest from the paired payment
            self.amount = (
                self.paired_internal_transfer_payment_id.amount
                + self.paired_internal_transfer_payment_id.fci_interest_amount
            )

        return move_vals
