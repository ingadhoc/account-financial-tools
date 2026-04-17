<<<<<<< faa0a9f3824392f23370f3c40193410b6cf2d92d
from odoo import fields, models


class AccountReconcileModel(models.Model):
    _inherit = "account.reconcile.model"

    shared_to_branches = fields.Boolean(
        related="match_journal_ids.shared_to_branches",
        store=True,
    )
||||||| 67cbc4687ef094aa05ec116b48aa81d42e93591c
=======
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################

from odoo import fields, models


class AccountReconcileModelPartnerMapping(models.Model):
    _inherit = "account.reconcile.model.partner.mapping"

    payment_ref_regex = fields.Char(help="The system will search for labels that start with the entered text")
>>>>>>> d1f2b6331760febc2d9705592b25dc548cbc7680
