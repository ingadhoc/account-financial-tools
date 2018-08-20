# © 2017 Eficent Business and IT Consulting Services S.L.
#        (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def action_open_reconcile(self):
        action_context = {
            'show_mode_selector': False, 'partner_ids': self.ids}
        if self._context.get('supplier_payments'):
            action_context['mode'] = 'suppliers'
        else:
            action_context['mode'] = 'customers'
        return {
            'type': 'ir.actions.client',
            'tag': 'manual_reconciliation_view',
            'context': action_context,
        }
