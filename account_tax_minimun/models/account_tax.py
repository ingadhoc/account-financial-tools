from odoo import models, fields

class AccountTax(models.Model):
    _inherit = 'account.tax'

    minimun_account_type = fields.Selection(
        [('net', 'Net Invoice'),
        ('total', 'Total Invoice'),
        ('tax_amount', 'Tax Amount'),
        ])
    minimun_amount = fields.Float(string="Minimun Amount")
    minimun_accumulate_period = fields.Selection([('monthy', 'Monthy')])
