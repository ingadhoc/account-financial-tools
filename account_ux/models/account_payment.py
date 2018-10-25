# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api
import datetime


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_liquidity_move_line_vals(self, amount):
        vals = super(AccountPayment, self)._get_liquidity_move_line_vals(
            amount)
        days_for_collection = False
        journal = self.journal_id
        if (self.payment_method_code == 'inbound_debit_card'):
            days_for_collection = journal.debit_card_days_for_collection
        elif (self.payment_method_code == 'inbound_credit_card'):
            days_for_collection = journal.credit_card_days_for_collection
        if days_for_collection:
            vals['date_maturity'] = fields.Date.to_string(
                fields.Date.from_string(
                    self.payment_date) + datetime.timedelta(days=10))
        return vals

    @api.multi
    def cancel(self):
        """
        On payment cancel delete move_name as we wont to allow deletion of
        payments. TODO: this could be parametrizable
        """
        res = super(AccountPayment, self).cancel()
        self.write({'move_name': False})
        return res
