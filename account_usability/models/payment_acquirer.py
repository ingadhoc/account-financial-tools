# -*- coding: utf-8 -*-
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class PaymentAcquirer(models.Model):
    _inherit = "payment.acquirer"

    journal_id = fields.Many2one(
        'account.journal',
        'Journal',
        help='Journal to be used to record journal entry of this payment '
        'acquirer'
    )

    @api.constrains('journal_id', 'company_id')
    def check_company(self):
        for rec in self:
            if (
                    rec.journal_id and rec.company_id and
                    rec.journal_id.company_id != rec.company_id):
                raise ValidationError(_(
                    'The journal company must belong to the same company of'
                    ' the aquirer'))
