# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    user_id = fields.Many2one(
        string='Contact Salesperson', related='partner_id.user_id', store=True,
        help='Salesperson of contact related to this journal item')
    # lo agregamos para que al agrupar en vista tree se vea y ademas que aparezca com messure en la pivot
    amount_residual_currency = fields.Monetary(
        group_operator='sum',
    )

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
        """
        Este metodo es el que se encarga de preparar los vals de la partial reconcile y también de los exchange diff.
        Extendemos la funcionalidad para el nuevo parametro "reconcile_on_company_currency" que nos permitiria
        conciliar sin tener en cuenta la moneda secundaria.
        Basicamente lo que hacemos en esta situacion es:
        a) Antes de llamar a super hacemos como si el par de apuntes a conciliar no tienen moneda de secundaria para
        que super concilie en moneda de la cia
        b) luego pos procesamos los vals que devuelve porque la conciliacion parcial siempre expresa los
        Debit Amount Currency y Credit Amount Currency en la moneda del apunte que esta conciliando, y con el parche
        de arriba super devuelve los importes en moneda de la compañía.
        Entonces lo que hacemos es luego calcular los importes en moneda secundaria usando la misma cotizacion del
        comprobante que se esta conciliando para que no sea necesario una diferencia de cambio.

        Dejamos algunos casos para explicar mejor este cambio:
        Caso 1:
        -------
        * Tengo un apunte de 100 USD a cotizacion 10 = 1000 ARS
        * Concilio contra un apunte de 500 ARS sin moneda secundaria pero en la fecha de este apunte la cotizacion es 20
        * Lo que haría odoo es:
            * considerar que esos 500 ARS a cotizacion 20 son 25 USD
            * descontaria 25 USD de deuda (el 25% de la deuda)
            * haría un asiento por diferencia de cambio para que la deuda en ARS represente también el 25%
            (es decir que quede 750 ARS de residual y no los 500 ARS nativos)
            * Odoo haría eso con dos partial reconcile, TODO compltar
        * Lo que hacemos nosotros es crear un partial reconcile que dice que:
            * se cancelan 500 ARS y cancela 50 USD (cnvertimos los ARS a la cotizacion del apunte que cancela)

        TODO escribir caso 2 (tanto apunte 1 como apunte 2 tienen moneda secundaria)
        """

        def get_accounting_rate(vals):
            if company_debit_currency.is_zero(abs(vals['aml'].balance)) or vals['currency'].is_zero(vals['aml'].amount_currency):
                return 0.0
            else:
                return abs(vals['aml'].amount_currency) / abs(vals['aml'].balance)

        company_debit_currency = debit_values['aml'].company_currency_id
        company_credit_currency = credit_values['aml'].company_currency_id
        reconcile_on_company_currency = debit_values['aml'].company_id.reconcile_on_company_currency and \
            (debit_values['aml'].currency_id != company_debit_currency or credit_values['aml'].currency_id != company_debit_currency) and \
            not debit_values['aml'].account_id.currency_id
        if reconcile_on_company_currency:
            shadowed_aml_values = {}
            if debit_values['aml'].currency_id != company_debit_currency:
                debit_values['original_currency'] = debit_values['aml'].currency_id
                debit_values['currency'] = company_debit_currency
                debit_values['amount_residual_currency'] = debit_values['amount_residual']
                shadowed_aml_values[debit_values['aml']] = {'currency_id': company_debit_currency,
                                                             'amount_residual_currency': debit_values['amount_residual']}
            if credit_values['aml'].currency_id != company_credit_currency:
                credit_values['original_currency'] = credit_values['aml'].currency_id
                credit_values['currency'] = company_credit_currency
                credit_values['amount_residual_currency'] = credit_values['amount_residual']
                shadowed_aml_values[credit_values['aml']] = {'currency_id': company_credit_currency,
                                                             'amount_residual_currency': credit_values['amount_residual']}
            res = super(AccountMoveLine, self.with_context(no_exchange_difference=True))._prepare_reconciliation_single_partial(debit_values, credit_values, shadowed_aml_values)
        else:
            res = super()._prepare_reconciliation_single_partial(debit_values, credit_values, shadowed_aml_values)

        if reconcile_on_company_currency and 'partial_values' in res:
            if 'original_currency' in credit_values:
                credit_values['currency'] = credit_values['original_currency']
                rate = get_accounting_rate(credit_values)
                res['partial_values']['credit_amount_currency'] = credit_values['aml'].currency_id.round(
                    res['partial_values']['credit_amount_currency'] * rate)
            if 'original_currency' in debit_values:
                debit_values['currency'] = debit_values['original_currency']
                rate = get_accounting_rate(debit_values)
                res['partial_values']['debit_amount_currency'] = credit_values['aml'].currency_id.round(
                    res['partial_values']['debit_amount_currency'] * rate)
        return res

    def _compute_amount_residual(self):
        """ Cuando se realiza un cobro de un recibo y el comprobante que se paga tiene moneda secundaria y queda totalmente conciliado en moneda de compañía pero no en moneda secundaria (ejemplo: diferencia de un centavo) lo que hacemos con este método es forzar que quede conciliado también en moneda secundaria. """
        super()._compute_amount_residual()
        need_amount_residual_currency_adjustment = self.filtered(lambda x: not x.reconciled and x.company_id.reconcile_on_company_currency and (x.account_id.reconcile or x.account_id.account_type in ('asset_cash', 'liability_credit_card')) and (x.company_currency_id or self.env.company.currency_id).is_zero(x.amount_residual) and not (x.currency_id or (x.company_currency_id or self.env.company.currency_id)).is_zero(x.amount_residual_currency))
        need_amount_residual_currency_adjustment.amount_residual_currency = 0.0
        need_amount_residual_currency_adjustment.reconciled = True
