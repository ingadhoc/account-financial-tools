# -*- coding: utf-8 -*-
from openerp import models, api


class AccountTaxWithholding(models.Model):
    _inherit = "account.tax.withholding"

    @api.multi
    def name_get(self):
        """
        No llamamos a super porque tendriamos que igualmente hacer un read
        para obtener la compania y no queremos disminuir la performance
        """
        res = []
        for record in self:
            record_name = '%s%s' % (
                record.description,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res
