# © 2022  ADHOC SA - MASTERCORE SAS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api
import datetime


class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"

    #This field is to be used by invoice in multicurrency
    selected_finacial_debt_currency = fields.Monetary(
        string='Selected Financial Debt in foreign currency',
        compute='_compute_selected_debt',
    )
    debt_multicurrency = fields.Boolean(
        string='debt is in foreign currency?', default=False,
    )
    selected_debt_currency_id = fields.Many2one("res.currency",
        string='Selected Debt in foreign currency',
    )

    @api.depends(
        'to_pay_move_line_ids.amount_residual',
        'to_pay_move_line_ids.amount_residual_currency',
        'to_pay_move_line_ids.currency_id',
        'to_pay_move_line_ids.move_id',
        'payment_date',
        'currency_id',
    )
    def _compute_selected_debt(self):
        for rec in self:
            selected_finacial_debt = 0.0
            selected_debt = 0.0
            selected_debt_untaxed = 0.0
            selected_debt_taxed = 0.0
            selected_finacial_debt_currency = 0.0
            for line in rec.to_pay_move_line_ids._origin:
                #this is conditional used to vat retention
                for abg in line.move_id.amount_by_group:
                    if str(abg[0]).find('IVA') > -1:
                        selected_debt_taxed += abg[1]
                selected_finacial_debt += line.financial_amount_residual
                # factor for total_untaxed
                invoice = line.move_id
                if line.currency_id != rec.company_id.currency_id:
                    selected_finacial_debt_currency += line.amount_residual_currency
                    rec.debt_multicurrency = True
                    rec.selected_debt_currency_id = line.move_id.currency_id.id
                elif line.currency_id != rec.company_id.currency_id and rec.debt_multicurrency:
                    selected_finacial_debt_currency += line.amount_residual_currency
                    rec.debt_multicurrency = True
                else:
                    rec.debt_multicurrency = False
                    #selected_debt += line.move_id.amount_residual
                selected_debt += line.amount_residual
                factor = invoice and invoice._get_tax_factor() or 1.0
                selected_debt_untaxed += line.amount_residual * factor
            sign = rec.partner_type == 'supplier' and -1.0 or 1.0
            rec.selected_finacial_debt = selected_finacial_debt * sign
            rec.selected_debt = selected_debt * sign
            rec.selected_finacial_debt_currency = selected_finacial_debt_currency * sign
            rec.selected_debt_untaxed = selected_debt_untaxed * sign
            rec.selected_debt_taxed = selected_debt_taxed
