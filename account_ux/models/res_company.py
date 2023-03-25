from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    reconcile_on_company_currency = fields.Boolean(
        help="When reconciling debt with secondary currency, if the account doesn't have a currency configured, then"
        " reconcile on company currency. This will avoid all the automatic exchange rates journal entries by forcing "
        " same rate of the original document being reconcile")
