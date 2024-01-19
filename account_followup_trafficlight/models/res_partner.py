from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    semaphore = fields.Selection(string='Semáforo', selection=[('1', '1 Mes'), ('2', '2 Meses'), ('3', '3 Meses'), ('999', '>= 4 Meses')])

