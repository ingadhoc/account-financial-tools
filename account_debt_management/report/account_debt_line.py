from odoo import tools, models, fields, api, _
from ast import literal_eval


class AccountDebtLine(models.Model):
    _name = "account.debt.line"
    _description = "Account Debt Line"
    _auto = False
    _rec_name = 'document_number'
    _order = 'date asc, date_maturity asc, document_number asc, id'
    _depends = {
        'res.partner': [
            'user_id',
        ],
        'account.move': [
            'document_type_id', 'document_number',
        ],
        'account.move.line': [
            'account_id', 'debit', 'credit', 'date_maturity', 'partner_id',
            'amount_currency',
        ],
    }

    blocked = fields.Boolean(
        string='No Follow-up',
        readonly=True,
        help="You can check this box to mark this journal item as a "
        "litigation with the associated partner"
    )
    document_type_id = fields.Many2one(
        'account.document.type',
        'Document Type',
        readonly=True
    )
    document_number = fields.Char(
        readonly=True,
        string='Document Number',
    )
    date = fields.Date(
        readonly=True
    )
    date_maturity = fields.Date(
        readonly=True
    )
    ref = fields.Char(
        'Reference',
        readonly=True
    )
    amount = fields.Monetary(
        readonly=True,
        currency_field='company_currency_id',
    )
    amount_residual = fields.Monetary(
        readonly=True,
        string='Residual Amount',
        currency_field='company_currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        'Currency',
        readonly=True
    )
    amount_currency = fields.Monetary(
        readonly=True,
        currency_field='currency_id',
    )
    amount_residual_currency = fields.Monetary(
        readonly=True,
        string='Residual Amount in Currency',
        currency_field='currency_id',
    )
    move_lines_str = fields.Char(
        'Entry Lines String',
        readonly=True
    )
    account_id = fields.Many2one(
        'account.account',
        'Account',
        readonly=True
    )
    internal_type = fields.Selection([
        ('receivable', 'Receivable'),
        ('payable', 'Payable')],
        'Type',
        readonly=True,
    )
    # move_state = fields.Selection(
    #     [('draft', 'Unposted'), ('posted', 'Posted')],
    #     'Status',
    #     readonly=True
    # )
    reconciled = fields.Boolean(
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Partner',
        readonly=True
    )
    account_type = fields.Many2one(
        'account.account.type',
        'Account Type',
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        readonly=True
    )

    # computed fields
    financial_amount = fields.Monetary(
        compute='_compute_move_lines_data',
        currency_field='company_currency_id',
    )
    financial_amount_residual = fields.Monetary(
        compute='_compute_move_lines_data',
        currency_field='company_currency_id',
    )
    # we get this line to make it easier to compute other lines
    # for debt lines, as we group by due date, we should have only one
    move_line_id = fields.Many2one(
        'account.move.line',
        string='Entry line',
        compute='_compute_move_lines_data',
    )
    move_line_ids = fields.One2many(
        'account.move.line',
        string='Entry lines',
        compute='_compute_move_lines_data',
    )
    move_id = fields.Many2one(
        'account.move',
        string='Entry',
        compute='_compute_move_lines_data',
    )
    move_ids = fields.One2many(
        'account.move',
        string='Entries',
        compute='_compute_move_lines_data',
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )
    payment_group_id = fields.Many2one(
        'account.payment.group',
        'Payment Group',
        compute='_compute_move_lines_data',
    )
    invoice_id = fields.Many2one(
        'account.invoice',
        'Invoice',
        compute='_compute_move_lines_data',
    )
    # es una concatenacion de los name de los move lines
    name = fields.Char(
        compute='_compute_move_lines_data',
    )
    statement_id = fields.Many2one(
        'account.bank.statement',
        'Statement',
        compute='_compute_move_lines_data',
    )

    # TODO por ahora, y si nadie lo extraña, vamos a usar document_number
    # en vez de este, alternativas por si se extraña:
    # si se extraña entonces tal vez mejor restaurarlo con otro nombre
    # @api.one
    # def get_display_name(self):
    #     # usamos display_name para que contenga doc number o name
    #     # luego si el ref es igual al name del move no lo mostramos
    #     display_name = self.move_id.display_name
    #     ref = False
    #     # because account voucher replace / with ''
    #     move_names = [self.move_id.name, self.move_id.name.replace('/', '')]
    #     # solo agregamos el ref del asiento o el name del line si son
    #     # distintos a el name del asiento
    #     if self.ref and self.ref not in move_names:
    #         ref = self.ref
    #     elif (
    #             self.move_line_id.name and
    #             self.move_line_id.name != '/' and
    #             self.move_line_id.name not in move_names):
    #         ref = self.move_line_id.name
    #     if ref:
    #         display_name = '%s (%s)' % (display_name, ref)
    #     self.display_name = display_name

    @api.multi
    @api.depends('move_lines_str')
    # @api.depends('amount', 'amount_currency')
    def _compute_move_lines_data(self):
        """
        If debt_together in context then we discount payables and make
        cumulative all together
        """
        for rec in self:
            # for compatibility with journal security or
            # mult-store module. We should only display debt
            # lines allowed to the user but as we dont have an stored way to
            # get the journals, we can't create a rule
            # we have try to overwrite search method and use the stored field
            # move_lines_str but we could nt find a way to make compare an
            # string list with the list of journals
            if isinstance(literal_eval(rec.move_lines_str), int):
                move_lines_str = [literal_eval(rec.move_lines_str)]
            elif isinstance(literal_eval(rec.move_lines_str), tuple):
                move_lines_str = list(literal_eval(rec.move_lines_str))
            else:
                continue
            # Use search to find only move_lines that the user allowed to read
            move_lines = rec.move_line_ids.search(
                [('id', 'in', move_lines_str)])

            rec.move_line_ids = move_lines
            rec.name = ', '.join(move_lines.filtered('name').mapped('name'))
            rec.move_ids = rec.move_line_ids.mapped('move_id')
            if len(rec.move_ids) == 1:
                rec.move_id = rec.move_ids

            if len(move_lines) == 1:
                # return one line or empty recordset
                rec.move_line_id = (
                    len(move_lines) == 1 and move_lines[0] or
                    rec.env['account.move.line'])

            invoice_id = rec.move_line_ids.mapped('invoice_id')
            rec.invoice_id = len(invoice_id) == 1 and invoice_id

            payment_group = rec.move_line_ids.mapped(
                'payment_id.payment_group_id')
            rec.payment_group_id = len(payment_group) == 1 and payment_group

            statement = rec.move_line_ids.mapped('statement_id')
            rec.statement_id = len(statement) == 1 and statement
            # invoices = rec.move_line_ids.mapped('invoice_id')
            # if len(invoices) == 1:
            #     rec.invoice_id = invoices

            # payment_groups = rec.move_line_ids.mapped(
            #     'payment_id.payment_group_id')
            # if len(payment_groups) == 1:
            #     rec.payment_group_id = payment_groups

            # statements = rec.move_line_ids.mapped('statement_id')
            # if len(statements) == 1:
            #     rec.statement_id = statements

            rec.financial_amount = sum(
                rec.move_line_ids.mapped('financial_amount'))
            rec.financial_amount_residual = sum(
                rec.move_line_ids.mapped('financial_amount_residual'))

    @api.model_cr
    def init(self):
        # pylint: disable=E8103
        tools.drop_view_if_exists(self._cr, self._table)
        date_maturity_type = self.env['ir.config_parameter'].sudo().get_param(
            'account_debt_management.date_maturity_type')
        if date_maturity_type == 'detail':
            params = ('l.date_maturity as date_maturity,', ', l.date_maturity')
        elif date_maturity_type == 'max':
            params = ('max(l.date_maturity) as date_maturity,', '')
        else:
            params = ('min(l.date_maturity) as date_maturity,', '')
        query = """
            SELECT
                -- es una funcion y se renumera constantemente, por eso
                -- necesita el over
                -- ROW_NUMBER() OVER (ORDER BY l.partner_id, am.company_id,
                --     l.account_id, l.currency_id, a.internal_type,
                --     a.user_type_id, c.document_number, am.document_type_id,
                --     l.date_maturity) as id,
                -- igualmente los move lines son unicos, usamos eso como id
                max(l.id) as id,
                string_agg(cast(l.id as varchar), ',') as move_lines_str,
                max(am.date) as date,
                %s
                am.document_type_id as document_type_id,
                c.document_number as document_number,
                bool_and(l.reconciled) as reconciled,
                -- l.blocked as blocked,
                -- si cualquier deuda esta bloqueada de un comprobante,
                -- toda deberia estar bloqueda
                bool_and(l.blocked) as blocked,

                -- TODO borrar, al final no pudimos hacerlo asi porque si no
                -- agrupamos por am.name, entonces todo lo que no tenga tipo
                -- de doc lo muestra en una linea. Y si lo agregamos nos quedan
                -- desagregados los multiples pagos (y otros similares)
                -- si devuelve '' el concat del prefix y number lo cambiamos
                -- por null y luego coalesce se encarga de elerig el name
                -- devolvemos el string_agg de am.name para no tener que
                -- agregarlo en la clausula del group by
                -- COALESCE(NULLIF(CONCAT(
                --     dt.doc_code_prefix, am.document_number), ''),
                --         string_agg(am.name, ',')) as document_number,

                string_agg(am.ref, ',') as ref,
                --am.state as move_state,
                --l.full_reconcile_id as full_reconcile_id,
                --l.reconciled as reconciled,
                -- l.reconcile_partial_id as reconcile_partial_id,
                l.partner_id as partner_id,
                am.company_id as company_id,
                a.internal_type as internal_type,
                -- am.journal_id as journal_id,
                -- p.fiscalyear_id as fiscalyear_id,
                -- am.period_id as period_id,
                l.account_id as account_id,
                --l.analytic_account_id as analytic_account_id,
                -- a.internal_type as type,
                a.user_type_id as account_type,
                l.currency_id as currency_id,
                sum(l.amount_currency) as amount_currency,
                sum(l.amount_residual_currency) as amount_residual_currency,
                sum(l.amount_residual) as amount_residual,
                --pa.user_id as user_id,
                sum(l.balance) as amount
                -- coalesce(l.debit, 0.0) - coalesce(l.credit, 0.0) as amount
            FROM
                account_move_line l
                left join account_account a on (l.account_id = a.id)
                left join account_move am on (am.id=l.move_id)
                -- left join account_period p on (am.period_id=p.id)
                -- left join res_partner pa on (l.partner_id=pa.id)
                left join account_document_type dt on (
                    am.document_type_id=dt.id)
                left join (
                    SELECT
                        COALESCE (NULLIF (CONCAT (
                            dt.doc_code_prefix, am.document_number), ''),
                            am.name) as document_number,
                        am.id
                    FROM
                        account_move am
                        left join account_document_type dt on (
                            am.document_type_id=dt.id)
                    ) c on l.move_id = c.id
            WHERE
                -- l.state != 'draft' and
                a.internal_type IN ('payable', 'receivable')
            GROUP BY
                l.partner_id, am.company_id, l.account_id, l.currency_id,
                a.internal_type, a.user_type_id, c.document_number,
                am.document_type_id %s
                -- dt.doc_code_prefix, am.document_number
        """ % params
        self._cr.execute("""CREATE or REPLACE VIEW %s as (%s
        )""" % (self._table, query))

    # TODO tal vez podamos usar métodos agregados por account_usability
    # que hacen exactamente esto
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
    def get_model_id_and_name(self):
        """
        Function used to display the right action on journal items on dropdown
        lists, in reports like general ledger
        """
        if self.statement_id:
            return [
                'account.bank.statement', self.statement_id.id,
                _('View Bank Statement'), False]
        if self.payment_group_id:
            return [
                'account.payment.group',
                self.payment_group_id.id,
                _('View Payment Group'), False]
        if self.invoice_id:
            view_id = self.invoice_id.get_formview_id()
            return [
                'account.invoice',
                self.invoice_id.id,
                _('View Invoice'),
                view_id]
        # TODO ver si implementamos que pasa cuando hay mas de un move
        return [
            'account.move',
            self.move_id.id,
            _('View Move'),
            False]
