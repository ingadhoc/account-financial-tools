##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    group_reference_on_tree_and_main_form = fields.Boolean(
        implied_group='account_ux.group_reference_on_tree_and_main_form',
        string='Invoice Reference/Description',
    )
