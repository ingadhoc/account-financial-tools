# flake8: noqa
# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, _
from odoo.tools import float_is_zero, float_compare
from datetime import date


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.multi
    def get_model_id_and_name(self):
        # Function used to display the right action on journal
        # items on dropdown lists, in reports like general ledger
        if self.statement_id:
            return ['account.bank.statement',
                    self.statement_id.id, _('View Bank Statement'), False]
        if self.payment_id:
            return ['account.payment',
                    self.payment_id.id, _('View Payment'), False]
        if self.invoice_id:
            view_id = self.invoice_id.get_formview_id()
            return ['account.invoice',
                    self.invoice_id.id, _('View Invoice'), view_id]
        return ['account.move', self.move_id.id, _('View Move'), False]

    @api.multi
    def action_open_related_document(self):
        self.ensure_one()
        # usamos lo que ya se usa en js para devolver la accion
        res_model, res_id, action_name, view_id = self.get_model_id_and_name()

        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_id': res_id,
            # 'view_id': res[0],
        }

    @api.multi
    def _reconcile_lines(self, debit_moves, credit_moves, field):
        """ Modificamos contexto para que odoo solo concilie el metodo
        auto_reconcile_lines teniendo en cuenta la moneda de cia si la cuenta
        no tiene moneda.
        Va de la mano de la modificación de "create" en
        account.partial.reconcile
        """
        if self and self[0].company_id.country_id == self.env.ref('base.ar') and not self[0].account_id.currency_id:
            field = 'amount_residual'
        return super()._reconcile_lines(debit_moves, credit_moves, field)

    @api.multi
    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        """ This is needed if you reconcile, for eg, 1 USD to 1 USD but in an ARS account, by default
        odoo make a full reconcile and exchange
        """
        if self and self[0].company_id.country_id == self.env.ref('base.ar') and not self[0].account_id.currency_id:
            self = self.with_context(no_exchange_difference=True)
        return super().reconcile(writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id)

    # PORT full reconcile from v13 to have the new key "no_exchange_difference"
    @api.multi
    def check_full_reconcile(self):
        """
        This method check if a move is totally reconciled and if we need to create exchange rate entries for the move.
        In case exchange rate entries needs to be created, one will be created per currency present.
        In case of full reconciliation, all moves belonging to the reconciliation will belong to the same account_full_reconcile object.
        """
        # Get first all aml involved
        todo = self.env['account.partial.reconcile'].search_read(['|', ('debit_move_id', 'in', self.ids), ('credit_move_id', 'in', self.ids)], ['debit_move_id', 'credit_move_id'])
        amls = set(self.ids)
        seen = set()
        while todo:
            aml_ids = [rec['debit_move_id'][0] for rec in todo if rec['debit_move_id']] + [rec['credit_move_id'][0] for rec in todo if rec['credit_move_id']]
            amls |= set(aml_ids)
            seen |= set([rec['id'] for rec in todo])
            todo = self.env['account.partial.reconcile'].search_read(['&', '|', ('credit_move_id', 'in', aml_ids), ('debit_move_id', 'in', aml_ids), '!', ('id', 'in', list(seen))], ['debit_move_id', 'credit_move_id'])

        partial_rec_ids = list(seen)
        if not amls:
            return
        else:
            amls = self.browse(list(amls))

        # If we have multiple currency, we can only base ourselve on debit-credit to see if it is fully reconciled
        currency = set([a.currency_id for a in amls if a.currency_id.id != False])
        multiple_currency = False
        if len(currency) != 1:
            currency = False
            multiple_currency = True
        else:
            currency = list(currency)[0]
        # Get the sum(debit, credit, amount_currency) of all amls involved
        total_debit = 0
        total_credit = 0
        total_amount_currency = 0
        maxdate = date.min
        to_balance = {}
        cash_basis_partial = self.env['account.partial.reconcile']
        for aml in amls:
            cash_basis_partial |= aml.move_id.tax_cash_basis_rec_id
            total_debit += aml.debit
            total_credit += aml.credit
            maxdate = max(aml.date, maxdate)
            total_amount_currency += aml.amount_currency
            # Convert in currency if we only have one currency and no amount_currency
            if not aml.amount_currency and currency:
                multiple_currency = True
                total_amount_currency += aml.company_id.currency_id._convert(aml.balance, currency, aml.company_id, aml.date)
            # If we still have residual value, it means that this move might need to be balanced using an exchange rate entry
            if aml.amount_residual != 0 or aml.amount_residual_currency != 0:
                if not to_balance.get(aml.currency_id):
                    to_balance[aml.currency_id] = [self.env['account.move.line'], 0]
                to_balance[aml.currency_id][0] += aml
                to_balance[aml.currency_id][1] += aml.amount_residual != 0 and aml.amount_residual or aml.amount_residual_currency

        # Check if reconciliation is total
        # To check if reconciliation is total we have 3 differents use case:
        # 1) There are multiple currency different than company currency, in that case we check using debit-credit
        # 2) We only have one currency which is different than company currency, in that case we check using amount_currency
        # 3) We have only one currency and some entries that don't have a secundary currency, in that case we check debit-credit
        #   or amount_currency.
        # 4) Cash basis full reconciliation
        #     - either none of the moves are cash basis reconciled, and we proceed
        #     - or some moves are cash basis reconciled and we make sure they are all fully reconciled

        digits_rounding_precision = amls[0].company_id.currency_id.rounding
        if (
                (
                    not cash_basis_partial or (cash_basis_partial and all([p >= 1.0 for p in amls._get_matched_percentage().values()]))
                ) and
                (
                    currency and float_is_zero(total_amount_currency, precision_rounding=currency.rounding) or
                    multiple_currency and float_compare(total_debit, total_credit, precision_rounding=digits_rounding_precision) == 0
                )
        ):

            exchange_move_id = False
            missing_exchange_difference = False
            # Eventually create a journal entry to book the difference due to foreign currency's exchange rate that fluctuates
            if to_balance and any([not float_is_zero(residual, precision_rounding=digits_rounding_precision) for aml, residual in to_balance.values()]):
                if not self.env.context.get('no_exchange_difference'):
                    exchange_move = self.env['account.move'].with_context(default_type='entry').create(
                        self.env['account.full.reconcile']._prepare_exchange_diff_move(move_date=maxdate, company=amls[0].company_id))
                    part_reconcile = self.env['account.partial.reconcile']
                    for aml_to_balance, total in to_balance.values():
                        if total:
                            rate_diff_amls, rate_diff_partial_rec = part_reconcile.create_exchange_rate_entry(aml_to_balance, exchange_move)
                            amls += rate_diff_amls
                            partial_rec_ids += rate_diff_partial_rec.ids
                        else:
                            aml_to_balance.reconcile()
                    exchange_move.post()
                    exchange_move_id = exchange_move.id
                else:
                    missing_exchange_difference = True
            if not missing_exchange_difference:
                #mark the reference of the full reconciliation on the exchange rate entries and on the entries
                self.env['account.full.reconcile'].create({
                    'partial_reconcile_ids': [(6, 0, partial_rec_ids)],
                    'reconciled_line_ids': [(6, 0, amls.ids)],
                    'exchange_move_id': exchange_move_id,
                })
