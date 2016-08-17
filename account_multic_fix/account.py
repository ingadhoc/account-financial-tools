# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
import openerp.addons.decimal_precision as dp


class account_invoice(models.Model):
    _inherit = "account.invoice"

    @api.multi
    def onchange_company_id(self, company_id, part_id, type, invoice_line, currency_id):
        if self.invoice_line:
            raise Warning(
                _('You cannot change the company of a invoice that has lines. You should delete them first.'))
        return super(account_invoice, self).onchange_company_id(company_id, part_id, type, invoice_line, currency_id)


class account_invoice_line(models.Model):
    _inherit = "account.invoice.line"

    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='', type='out_invoice',
                          partner_id=False, fposition_id=False, price_unit=False, currency_id=False,
                          company_id=None):
        res = super(account_invoice_line, self).product_id_change(product, uom_id, qty=qty, name=name, type=type,
                                                                  partner_id=partner_id, fposition_id=fposition_id, price_unit=price_unit, currency_id=currency_id,
                                                                  company_id=company_id)
        if not 'value' in res:
            res['value'] = {}

        fpos = self.env['account.fiscal.position'].browse(fposition_id)
        if 'invoice_line_tax_id' in res['value']:
            tax_ids = res['value']['invoice_line_tax_id']
            taxes = self.env['account.tax'].search(
                [('id', 'in', tax_ids), ('company_id', '=', company_id)])
            taxes = fpos.map_tax(taxes)
            res['value']['invoice_line_tax_id'] = taxes.ids
        return res


class account_move_line(models.Model):
    _inherit = "account.move.line"

    analytic_account_id = fields.Many2one(
        domain="[('company_id','=',company_id), ('type', '!=', 'view')]")


class account_move(models.Model):
    _inherit = "account.move"

    period_id = fields.Many2one(
        domain="[('company_id','=',company_id), ('state', '=', 'draft')]")

    @api.model
    def create(self, vals):
        """
        Fix manual reonciliation from parent company.
        En la linea "writeoff_move_id = move_obj.create(cr, uid, {" de move
        line esta faltando el contexto que se peirde al llegar al create del
        move, a su vez, y la compania no viene seteada en vals ni en contexto
        la perdemos completamente, y terminand asignando la del usuario
        por eso hacemos este truco que chequea si periodo y diario son de la
        misma cia y fuerza compania de ese tipo
        """
        if not vals.get('company_id', False):
            journal_id = vals.get('journal_id', False)
            period_id = vals.get('period_id', False)
            if journal_id and period_id:
                journal = self.env['account.journal'].browse(journal_id)
                period = self.env['account.period'].browse(period_id)
                if period.company_id == journal.company_id:
                    vals['company_id'] = journal.company_id.id
        return super(account_move, self).create(vals)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        self.period_id = False
        if self.journal_id:
            self.company_id = self.journal_id.company_id.id
            periods = self.with_context(
                company_id=self.journal_id.company_id.id).env['account.period'].find()
            self.period_id = periods and periods[0].id or False


class account_statement(models.Model):
    _inherit = "account.bank.statement"

    period_id = fields.Many2one(
        domain="[('company_id','=',company_id), ('state', '=', 'draft')]")

    @api.multi
    def onchange_journal_id(self, journal_id):
        res = super(account_statement, self).onchange_journal_id(journal_id)
        if journal_id:
            periods = self.with_context(
                company_id=self.env['account.journal'].browse(journal_id).company_id.id).env['account.period'].find()
            res['value']['period_id'] = periods and periods[0].id or False
        return res

    def _check_company_id(self, cr, uid, ids, context=None):
        for statement in self.browse(cr, uid, ids, context=context):
            if statement.journal_id.company_id.id != statement.period_id.company_id.id:
                return False
        return True

    _constraints = [
            (_check_company_id, 'The journal and period chosen have to belong to the same company.', [
             'journal_id', 'period_id']),
        ]


class account_bank_statement_line(models.Model):
    _inherit = "account.bank.statement.line"

    def _domain_move_lines_for_reconciliation(self, cr, uid, st_line, excluded_ids=None, str=False, additional_domain=None, context=None):
        domain = super(account_bank_statement_line, self)._domain_move_lines_for_reconciliation(cr, uid, st_line, excluded_ids, str, additional_domain, context)
        domain.append(('company_id', '=', st_line.statement_id.company_id.id))
        return domain

    def _domain_reconciliation_proposition(self, cr, uid, st_line, excluded_ids=None, context=None):
        domain = super(account_bank_statement_line, self)._domain_reconciliation_proposition(cr, uid, st_line, excluded_ids, context)
        domain.append(('company_id', '=', st_line.statement_id.company_id.id))
        return domain


class AccountStatementOperationTemplate(models.Model):
    _inherit = 'account.statement.operation.template'

    company_id = fields.Many2one(
        'res.company', string='Company', related='account_id.company_id',
        store=True)
