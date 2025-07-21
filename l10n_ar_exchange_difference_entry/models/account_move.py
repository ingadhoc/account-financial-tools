from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    original_documents_ids = fields.Many2many(
        "account.move",
        compute="_compute_original_documents_id",
        help="The original invoice and payment related to this exchange difference entry.",
    )
    can_create_debit_note = fields.Boolean(
        compute="_compute_can_create_debit_note",
        store=True,
        help="Indicates if this exchange difference entry can be converted to a debit note.",
    )

    @api.model
    def action_exchange_difference(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "name": "Exchange Difference",
            "view_mode": "list,form",
            "views": [
                (self.env.ref("l10n_ar_exchange_difference_entry.view_invoice_exchange_list").id, "list"),
                (self.env.ref("account.view_move_form").id, "form"),
            ],
            "context": {
                "currency_exchange_journal_id": self.env.company.currency_exchange_journal_id.id,
            },
            "domain": [
                ("move_type", "=", "entry"),
                ("reversed_entry_id", "=", False),
                ("reversal_move_ids", "=", False),
                ("journal_id", "=", self.env.company.currency_exchange_journal_id.id),
                ("can_create_debit_note", "=", True),
            ],
        }

    def action_open_exchange_difference_wizard(self):
        """Server action to open the Exchange Difference Wizard."""
        move_ids = self.env.context.get("active_ids", [])
        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ar.exchange.difference.wizard",
            "view_mode": "form",
            "target": "new",
            "name": "Convert to Debit Note",
            "context": {
                "default_move_ids": [(6, 0, move_ids)],
            },
        }

    def _compute_original_documents_id(self):
        for move in self:
            partial_reconcile = self.env["account.partial.reconcile"].search([("exchange_move_id.id", "=", move.id)])
            move.original_documents_ids = partial_reconcile.mapped("debit_move_id.move_id") | partial_reconcile.mapped(
                "credit_move_id.payment_id.move_id"
            )

    def _compute_can_create_debit_note(self):
        for move in self:
            line = move.line_ids.filtered(lambda x: x.account_type == "asset_receivable")
            move.can_create_debit_note = line.debit > 0.0
