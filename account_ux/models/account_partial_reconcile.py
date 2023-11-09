from odoo import models, api


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    #TODO revisar la compatibilidad de esta funcion con el diferencial de cambio
    # @API.MODEL
    # DEF CREATE(SELF, VALS):
    #     """ ADEMAS DE MANDAR EN EL CONTEXTO EN EL METODO RECONCILE, HACEMOS
    #     QUE EL PARTIAL RECONCILE QUE CREA EL METODO AUTO_RECONCILE_LINES
    #     NO TENGA MONEDA EN LA MISMA SITUACIÓN (PODRIAMOS ).
    #     VA DE LA MANO DE LA MODIFICACION DE "DEF RECONCILE" EN AML
    #     """
    #     IF VALS.GET('CURRENCY_ID'):
    #         ACCOUNT = SELF.ENV['ACCOUNT.MOVE.LINE'].BROWSE(VALS.GET('DEBIT_MOVE_ID')).ACCOUNT_ID
    #         IF ACCOUNT.COMPANY_ID.COUNTRY_ID == SELF.ENV.REF('BASE.AR') AND NOT ACCOUNT.CURRENCY_ID:
    #             VALS.UPDATE({'CURRENCY_ID': FALSE, 'AMOUNT_CURRENCY': 0.0})
    #     RETURN SUPER().CREATE(VALS)
