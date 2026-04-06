from odoo import fields, models


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    shared_to_branches = fields.Boolean(
        related="match_journal_ids.shared_to_branches",
        store=True,
    )
