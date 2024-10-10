from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    surcharge_ids = fields.One2many(
        'account.payment.term.surcharge',
        'payment_term_id', string='Surcharges',
        copy=True,
    )

    show_surcharge_warning = fields.Boolean(compute='_compute_surcharge_product')

    @api.depends('company_id', 'surcharge_ids')
    def _compute_surcharge_product(self):
        """Check if the surcharge product needs to be updated for the given company context."""
        for rec in self:
            if rec.surcharge_ids:
                if rec.company_id:  # Verificar para una compañía específica
                    company = rec.company_id
                    # Devuelve False si falta el producto de recargo
                    self.show_surcharge_warning = bool(company.payment_term_surcharge_product_id)
                else:  # Verificar todas las compañías si company_id es False
                    all_companies = self.env['res.company'].search([])
                    # Devuelve False si alguna compañía no tiene configurado el producto de recargo
                    rec.show_surcharge_warning = all(company.payment_term_surcharge_product_id for company in all_companies)
            else:
                rec.show_surcharge_warning = True
