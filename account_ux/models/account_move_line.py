# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_compare
from datetime import date


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    user_id = fields.Many2one(
        string='Contact Salesperson', related='partner_id.user_id', store=True,
        help='Salesperson of contact related to this journal item')
