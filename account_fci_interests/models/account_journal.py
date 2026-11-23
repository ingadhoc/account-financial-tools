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
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_fci_journal = fields.Boolean(
        string="Is FCI Journal",
        default=False,
        help="If enabled, this journal is used to manage a Mutual Investment Fund (FCI).",
    )
    fci_income_account_id = fields.Many2one(
        comodel_name="account.account",
        string="FCI Income Account",
        domain="[('internal_group', '=', 'income')]",
        check_company=True,
        help="Income account used to record accrued interest on FCI withdrawals.",
    )

    @api.constrains("is_fci_journal", "type")
    def _check_fci_journal_type(self):
        for journal in self:
            if journal.is_fci_journal and journal.type != "cash":
                raise ValidationError(
                    _(
                        "Journal '%(name)s' is marked as FCI Journal but is not of type 'Cash'. "
                        "An FCI journal must be of type Cash.",
                        name=journal.display_name,
                    )
                )

    def action_fci_withdraw(self):
        """Open a pre-filled internal transfer form from this FCI journal."""
        self.ensure_one()
        return {
            "name": _("Withdraw FCI / Accrue Interest"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_is_internal_transfer": True,
                "default_journal_id": self.id,
                "default_payment_type": "outbound",
            },
        }
