# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields


class account_move(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'mail.thread']

    name = fields.Char(track_visibility='onchange')
    ref = fields.Char(track_visibility='onchange')
    journal_id = fields.Many2one(track_visibility='onchange')
    state = fields.Selection(track_visibility='onchange')
    # because message is not undersandable, we should do it in another way
    # line_id = fields.One2many(track_visibility='onchange')
    to_check = fields.Boolean(track_visibility='onchange')
    partner_id = fields.Many2one(track_visibility='onchange')
    amount = fields.Float(track_visibility='onchange')
    date = fields.Date(track_visibility='onchange')
    narration = fields.Text(track_visibility='onchange')
    company_id = fields.Many2one(track_visibility='onchange')
    balance = fields.Float(track_visibility='onchange')

    # este todavia es necesario en v9 pero por ahora omitimos, probablemente
    # en v10 no sea mas necesario
    # @api.multi
    # def button_cancel(self):
    #     res = super(account_move, self).button_cancel()
    #     tracked_fields = self._get_tracked_fields('state')
    #     initial_values = {self.id: {'state': 'posted'}}
    #     self.message_track(tracked_fields, initial_values)
    #     return res
