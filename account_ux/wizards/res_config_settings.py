##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    reconcile_on_company_currency = fields.Boolean(
        related='company_id.reconcile_on_company_currency', readonly=False)
