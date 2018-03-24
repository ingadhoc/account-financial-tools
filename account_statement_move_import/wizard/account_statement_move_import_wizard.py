##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import Warning
from dateutil.relativedelta import relativedelta


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
    def onchange(self, values, field_name, field_onchange):
        """
        Idea obtenida de aca
        https://github.com/odoo/odoo/issues/16072#issuecomment-289833419
        por el cambio que se introdujo en esa mimsa conversación, TODO en v11
        no haría mas falta, simplemente domain="[('id', 'in', x2m_field)]"
        Otras posibilidades que probamos pero no resultaron del todo fue:
        * agregar onchange sobre campos calculados y que devuelvan un dict con
        domain. El tema es que si se entra a un registro guardado el onchange
        no se ejecuta
        * usae el modulo de web_domain_field que esta en un pr a la oca
        """
        for field in field_onchange.keys():
            if field.startswith('journal_account_ids.'):
                del field_onchange[field]
        return super(account_statement_move_import_wizard, self).onchange(
            values, field_name, field_onchange)

    @api.multi
    @api.onchange('statement_id')
    def onchange_statement(self):
        if self.statement_id.date:
            date = fields.Date.from_string(self.statement_id.date)
            self.from_date = date + relativedelta(day=1)
            self.to_date = date + relativedelta(day=1, months=+1, days=-1)

    @api.multi
    @api.depends('statement_id')
    def get_journal(self):
        self.journal_id = self.statement_id.journal_id

    @api.multi
    # @api.onchange('from_date', 'to_date', 'journal_id')
    def get_move_lines(self):
        # dont know why but on v9 the onchange does not work and move_line_ids
        # remains empty on wizard confirmation
        move_lines = self.move_line_ids.search([
            ('journal_id', '=', self.journal_id.id),
            ('account_id', 'in', self.journal_account_ids.ids),
            ('statement_id', '=', False),
            ('exclude_on_statements', '=', False),
            # agregamos esta condicion porque hasta v10, inclusive, no se
            # permite que un move este en mas de un statement, entonces
            # solo ofrecemos lineas si el move no está en ningún statement
            ('move_id.statement_line_id', '=', False),
            ('date', '>=', self.from_date),
            ('date', '<=', self.to_date),
        ])
        self.move_line_ids = move_lines
        return {
            'type': 'ir.actions.act_window',
            'name': 'Statement Import Journal Items Wizard',
            'res_model': 'account.statement.move.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

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
        statement_currency = statement.currency_id
        company_currency = statement.company_id.currency_id
        moves = self.env['account.move']
        for line in self.move_line_ids:
            # como odoo move solo en un extracto si ya se importo el move
            # no volvemos a importar. TODO ver como sigue esto en v11
            if line.move_id in moves:
                continue
            moves |= line.move_id
            if line.account_id not in self.journal_account_ids:
                raise Warning(_(
                    'Imported line account must be one of the journals '
                    'defaults, in this case %s') % (
                    ', '.join(self.journal_account_ids.mapped('name'))))

            if line.statement_id:
                raise Warning(_(
                    'Imported line must have "statement_id" == False'))

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
                amount = line.balance
                currency_id = line.currency_id.id
                amount_currency = line.amount_currency

            line_vals = {
                'statement_id': statement.id,
                'date': line.date,
                'name': line.name,
                'ref': line.ref,
                'amount': amount,
                'currency_id': currency_id,
                'amount_currency': amount_currency,
                'partner_id': line.partner_id.id,
            }

            # create statement line
            statement_line = statement.line_ids.create(line_vals)
            line.move_id.statement_line_id = statement_line.id
            line.statement_id = statement.id
        return True
