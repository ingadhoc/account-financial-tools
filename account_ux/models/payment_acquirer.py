# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, _
from odoo.exceptions import ValidationError


class PaymentAcquirer(models.Model):
    _inherit = "payment.acquirer"

    @api.constrains('journal_id', 'company_id')
    def check_company(self):
        for rec in self:
            if (
                    rec.journal_id and rec.company_id and
                    rec.journal_id.company_id != rec.company_id):
                raise ValidationError(_(
                    'The journal company must belong to the same company of'
                    ' the aquirer'))
