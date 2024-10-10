from odoo import models


class ResCompanyInterest(models.Model):
    _inherit = 'res.company.interest'

    def _prepare_interest_invoice(self, partner, debt, to_date, journal):
        res = super()._prepare_interest_invoice(partner, debt, to_date, journal)

        res.update({
            'is_move_sent': True,
        })
        return res
