from odoo import models, api, fields


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Todo esto es para arreglar dos cosas en odoo que parecen estar provocadas porque el campo journal_id es heredado
    # desde move. Eso provoca que
    # 1. Cambiar el journal_id, si bien recomputa nevos avaialble payment methods, no devuelve nada al cliente y
    # entonces la lista de available payment methods no se actualiza y por ende el payment method tampoco
    # 2. agregando el campo journal como computado se arreglar (related no funcionó). Pero al hacer esto necesitamos
    # también...
    # 3. extender _compute_available_journal_ids porque en realidad la compañía es computada desde el journal, pero a
    # la vez los available payment methods son computados desde la company. Entonces basicamente si no tenemos company
    # le ponemos la del enviroment
    # 4. Tambien mejoramos que si cambian los available payment methods y el diario seleccionado no satisface, se
    # seleccione uno que si pueda ser seleccionado
    journal_id = fields.Many2one(
        'account.journal',
        readonly=False,
        compute='_compute_journal_id', inverse='_inverse_journal_id', search='_search_journal_id',
        required=True,
        states={'draft': [('readonly', False)]},
    )

    def _search_journal_id(self, operator, value):
        return [('move_id.journal_id', operator, value)]

    def _inverse_journal_id(self):
        for rec in self:
            rec.move_id.journal_id = self.journal_id

    @api.depends('available_journal_ids')
    def _compute_journal_id(self):
        for rec in self:
            if rec.move_id.journal_id not in self.available_journal_ids._origin:
                rec.journal_id = self.available_journal_ids._origin[:1]
            else:
                rec.journal_id = rec.move_id.journal_id

    @api.depends('payment_type')
    def _compute_available_journal_ids(self):
        for pay in self:
            if not pay.company_id:
                pay.company_id = self.env.company
        return super()._compute_available_journal_ids()
