# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api, _
from openerp.exceptions import Warning


class account_statement_move_import_wizard(models.TransientModel):
    _name = "account.statement.move.import.wizard"
    _description = "account_statement_move_import_wizard"

    @api.model
    def _get_statement(self):
        return self.env['account.bank.statement'].browse(
            self._context.get('active_id', False))

    from_date = fields.Date(
        'From Date',
        required=True,
        )
    to_date = fields.Date(
        'To Date',
        required=True,
        )
    statement_id = fields.Many2one(
        'account.bank.statement',
        'Statement',
        default=_get_statement,
        required=True,
        ondelete='cascade',
        )
    journal_id = fields.Many2one(
        'account.journal',
        _('Journal'),
        compute='get_journal',
        )
    journal_account_ids = fields.Many2many(
        'account.account',
        compute='get_accounts',
        string=_('Journal Accounts')
        )
    move_line_ids = fields.Many2many(
        'account.move.line',
        'account_statement_import_move_line_rel',
        'line_id', 'move_line_id',
        'Journal Items',
        domain="[('journal_id', '=', journal_id), "
        "('statement_id', '=', False), "
        # mostramos los que se excluyen por defecto
        # "('exclude_on_statements', '=', False), "
        "('account_id', 'in', journal_account_ids[0][2])]"
        )

    @api.multi
    @api.onchange('statement_id')
    def onchange_statement(self):
        self.from_date = self.statement_id.period_id.date_start
        self.to_date = self.statement_id.period_id.date_stop

    @api.multi
    @api.depends('statement_id')
    def get_journal(self):
        self.journal_id = self.statement_id.journal_id

    @api.onchange('from_date', 'to_date', 'journal_id')
    def get_move_lines(self):
        move_lines = self.move_line_ids.search([
            ('journal_id', '=', self.journal_id.id),
            ('account_id', 'in', self.journal_account_ids.ids),
            ('statement_id', '=', False),
            ('exclude_on_statements', '=', False),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date),
            ])
        self.move_line_ids = move_lines

    @api.multi
    @api.depends('journal_id')
    def get_accounts(self):
        self.journal_account_ids = (
            self.journal_id.default_credit_account_id +
            self.journal_id.default_debit_account_id)

    @api.multi
    def confirm(self):
        self.ensure_one()

        statement = self.statement_id
        statement_currency = statement.currency
        company_currency = statement.company_id.currency_id
        for line in self.move_line_ids:
            if line.account_id not in self.journal_account_ids:
                raise Warning(_(
                    'Imported line account must be one of the journals '
                    'defaults, in this case %s') % (
                    ', '.join(self.journal_account_ids.mapped('name'))))

            if line.statement_id:
                raise Warning(_(
                    'Imported line must have "statement_id" == False'))

            line_balance = line.debit - line.credit
            # if line_balance > 0:
            #     line_type = 'customer'
            # else:
            #     line_type = 'supplier'

            # si el statement es en otra moneda, odoo interpreta que el amount
            # de las lineas es en esa moneda y no tendria sentido importar
            # otra moneda, ademas si uno hace un pago en otra moneda odoo
            # convierte la linea que afecta el banco a la moneda del banco
            if statement_currency != company_currency:
                if line.currency_id != statement_currency:
                    raise Warning(
                        'Si el diario del extracto es en otra moneda distinta '
                        'a la de la compañía, los apuntes a importar deben '
                        'tener como otra moneda esa misma moneda (%s)' % (
                            statement_currency.name))
                amount = line.amount_currency
                currency_id = False
                amount_currency = False
            # si el estatement es en moneda de la cia, importamos por las dudas
            # currency y amount currency pero en realidad no son necesarios
            # y de hecho son invisibles por defecto
            else:
                amount = line_balance
                currency_id = line.currency_id.id
                amount_currency = line.amount_currency

            line_vals = {
                'statement_id': statement.id,
                'date': line.date,
                'name': line.name,
                'ref': line.ref,
                'amount': amount,
                'imported': True,
                'imported_line_id': line.id,
                'currency_id': currency_id,
                'amount_currency': amount_currency,
                # 'type': line_type,
                'partner_id': line.partner_id.id,
                # we need journal entry so that id dont suggest a
                # reconciliation
                'journal_entry_id': line.move_id.id,
                }

            # create statement line
            statement.line_ids.create(line_vals)

            # add statement to move lines
            line.write({'statement_id': statement.id})
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
