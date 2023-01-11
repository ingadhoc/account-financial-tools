from odoo import fields, models


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    surcharge_ids = fields.One2many(
        'account.payment.term.surcharge',
        'payment_term_id', string='Surcharges',
        copy=True,
    )
