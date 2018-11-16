# Copyright 2015 ADHOC SA  (http://www.adhoc.com.ar)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'mail.thread']

    name = fields.Char(track_visibility='onchange')
    ref = fields.Char(track_visibility='onchange')
    journal_id = fields.Many2one(track_visibility='onchange')
    state = fields.Selection(track_visibility='onchange')
    to_check = fields.Boolean(track_visibility='onchange')
    partner_id = fields.Many2one(track_visibility='onchange')
    amount = fields.Float(track_visibility='onchange')
    date = fields.Date(track_visibility='onchange')
    narration = fields.Text(track_visibility='onchange')
    company_id = fields.Many2one(track_visibility='onchange')
    balance = fields.Float(track_visibility='onchange')
