##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################

from odoo import fields, models


class AccountReconcileModelPartnerMapping(models.Model):
    _inherit = "account.reconcile.model.partner.mapping"

    payment_ref_regex = fields.Char(help="The system will search for labels that start with the entered text")
