# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    user_id = fields.Many2one(
        string='Contact Salesperson', related='partner_id.user_id', store=True,
        help='Salesperson of contact related to this journal item')

    def _compute_amount_residual(self):
        """ Cuando se realiza un cobro de un recibo y el comprobante que se paga tiene moneda secundaria y queda totalmente conciliado en moneda de compañía pero no en moneda secundaria (ejemplo: diferencia de un centavo) lo que hacemos con este método es forzar que quede conciliado también en moneda secundaria. """
        super()._compute_amount_residual()
        need_amount_residual_currency_adjustment = self.filtered(lambda x: not x.reconciled and x.company_id.reconcile_on_company_currency and (x.account_id.reconcile or x.account_id.account_type in ('asset_cash', 'liability_credit_card')) and (x.company_currency_id or self.env.company.currency_id).is_zero(x.amount_residual) and not (x.currency_id or (x.company_currency_id or self.env.company.currency_id)).is_zero(x.amount_residual_currency))
        need_amount_residual_currency_adjustment.amount_residual_currency = 0.0
        need_amount_residual_currency_adjustment.reconciled = True
