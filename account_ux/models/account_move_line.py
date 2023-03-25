# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    user_id = fields.Many2one(
        string='Contact Salesperson', related='partner_id.user_id', store=True,
        help='Salesperson of contact related to this journal item')

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals):
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
            if company_currency.is_zero(vals['balance']) or vals['currency'].is_zero(vals['amount_currency']):
                return 0.0
            else:
                return abs(vals['amount_currency']) / abs(vals['balance'])

        company_currency = debit_vals['company'].currency_id
        reconcile_on_company_currency = debit_vals['company'].reconcile_on_company_currency and \
            (debit_vals['currency'] != company_currency or credit_vals['currency'] != company_currency) and \
            not debit_vals['record'].account_id.currency_id
        if reconcile_on_company_currency:
            if debit_vals['currency'] != debit_vals['company'].currency_id:
                debit_vals['original_currency'] = debit_vals['currency']
                debit_vals['original_amount_residual_currency'] = debit_vals['amount_residual_currency']
                debit_vals['currency'] = debit_vals['company'].currency_id
                debit_vals['amount_residual_currency'] = debit_vals['amount_residual']
            if credit_vals['currency'] != credit_vals['company'].currency_id:
                credit_vals['original_currency'] = credit_vals['currency']
                credit_vals['original_amount_residual_currency'] = credit_vals['amount_residual_currency']
                credit_vals['currency'] = credit_vals['company'].currency_id
                credit_vals['amount_residual_currency'] = credit_vals['amount_residual']
        res = super()._prepare_reconciliation_single_partial(debit_vals, credit_vals)

        if reconcile_on_company_currency:
            if 'original_currency' in credit_vals:
                credit_vals['currency'] = credit_vals['original_currency']
                rate = get_accounting_rate(credit_vals)
                res['partial_vals']['credit_amount_currency'] = credit_vals['currency'].round(
                    res['partial_vals']['credit_amount_currency'] * rate)
            if 'original_currency' in debit_vals:
                debit_vals['currency'] = debit_vals['original_currency']
                rate = get_accounting_rate(debit_vals)
                res['partial_vals']['debit_amount_currency'] = credit_vals['currency'].round(
                    res['partial_vals']['debit_amount_currency'] * rate)
        return res
