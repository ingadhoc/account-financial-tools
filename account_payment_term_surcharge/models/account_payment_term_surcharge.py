from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class AccountPaymentTermSurcharge(models.Model):

    _name = 'account.payment.term.surcharge'
    _description = 'Payment Terms Surcharge'
    _order = 'sequence, id'

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', required=True, index=True, ondelete='cascade')
    surcharge = fields.Float(string="Surcharge [%]")
    days = fields.Integer(string='Number of Days', required=True, default=0)
    day_of_the_month = fields.Integer(string='Day of the month', help="Day of the month on which the invoice must come to its term. If zero or negative, this value will be ignored, and no specific day will be set. If greater than the last day of a month, this number will instead select the last day of this month.")
    option = fields.Selection([
            ('day_after_invoice_date', "days after the invoice date"),
            ('after_invoice_month', "days after the end of the invoice month"),
            ('day_following_month', "of the following month"),
            ('day_current_month', "of the current month"),
        ],
        default='day_after_invoice_date', required=True, string='Options'
        )
    sequence = fields.Integer(default=10, help="Gives the sequence order when displaying a list of payment terms lines.")

    @api.constrains('surcharge')
    def _check_percent(self):
        for term_surcharge in self:
            if (term_surcharge.surcharge < 0.0 or term_surcharge.surcharge > 100.0):
                raise ValidationError(_('Percentages on the Payment Terms lines must be between 0 and 100.'))

    @api.constrains('days')
    def _check_days(self):
        for term_surcharge in self:
            if term_surcharge.option in ('day_following_month', 'day_current_month') and term_surcharge.days <= 0:
                raise ValidationError(_("The day of the month used for this term must be strictly positive."))
            elif term_surcharge.days < 0:
                raise ValidationError(_("The number of days used for a payment term cannot be negative."))

    @api.onchange('option')
    def _onchange_option(self):
        if self.option in ('day_current_month', 'day_following_month'):
            self.days = 0

    def _calculate_date(self, date_ref=None):
        ''' Se retorna la fecha de un recargo segun una fecha dada, esto se hace
        teniendo en cuenta la configuracion propia del recargo. '''
        date_ref = date_ref or fields.Date.today()
        next_date = fields.Date.from_string(date_ref)
        if self.option == 'day_after_invoice_date':
            next_date += relativedelta(days=self.days)
            if self.day_of_the_month > 0:
                months_delta = (self.day_of_the_month < next_date.day) and 1 or 0
                next_date += relativedelta(day=self.day_of_the_month, months=months_delta)
        elif self.option == 'after_invoice_month':
            next_first_date = next_date + relativedelta(day=1, months=1)  # Getting 1st of next month
            next_date = next_first_date + relativedelta(days=self.days - 1)
        elif self.option == 'day_following_month':
            next_date += relativedelta(day=self.days, months=1)
        elif self.option == 'day_current_month':
            next_date += relativedelta(day=self.days, months=0)
        return next_date
