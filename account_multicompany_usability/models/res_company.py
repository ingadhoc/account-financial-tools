# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api, _
from openerp.exceptions import Warning
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    short_name = fields.Char(
        help='Short name used to identify this company',
    )

    @api.multi
    def get_company_sufix(self):
        # cuando pedimos para unr registro que no tiene sia no queremos
        # que ensure_one arroje error
        if (
                len(self) != 1 or
                self._context.get('no_company_sufix') or
                not self.env.user.has_group('base.group_multi_company')):
            return ''
        else:
            return ' (%s)' % (self.short_name or self.name)

    consolidation_company = fields.Boolean(
        'Consolidation Company',
    )

    @api.one
    def _recreate_properties(self, from_companies):
        _logger.info('Re creating properties')
        todo_list = [
            ('property_account_receivable', 'res.partner', 'account.account'),
            ('property_account_payable', 'res.partner', 'account.account'),
            ('property_account_expense_categ',
                'product.category', 'account.account'),
            ('property_account_income_categ',
                'product.category', 'account.account'),
            # with category should be ok
            # ('property_account_expense',
            #     'product.template', 'account.account'),
            # ('property_account_income',
            #     'product.template', 'account.account'),
        ]
        for record in todo_list:
            # buscamos el campo para la property
            field = self.env['ir.model.fields'].search([
                ('name', '=', record[0]),
                ('model', '=', record[1]),
                ('relation', '=', record[2])], limit=1)
            # buscamos una property de companias hijas y sin recurso
            prop = self.env['ir.property'].search([
                ('name', '=', record[0]),
                ('fields_id', '=', field.id),
                ('res_id', '=', False),
                ('company_id', 'in', self.child_ids.ids),
            ], limit=1)
            if not prop:
                raise Warning(_(
                    'No encontramos ninguna property en las cias hijas para'
                    '%s') % (record[0]))
            else:
                # obtenemos value para nueva propertie
                model, resource_id = prop.value_reference.split(',')
                if model != 'account.account':
                    raise Warning(_(
                        'La property encontrada no es de account.account'))
                child_c_account = self.env[model].browse(int(resource_id))
                parent_c_account = self.env[model].search([
                    ('code', '=', child_c_account.code),
                    ('company_id', '=', self.id)], limit=1)
                if not parent_c_account:
                    raise Warning(_(
                        'No encontramos cuenta en la cia padre para cuenta '
                        'property "%s"') % (child_c_account.code))
                value = 'account.account,' + str(parent_c_account.id)

                # creamos la property
                prop = prop.create({
                    'name': record[0],
                    'company_id': self.id,
                    'fields_id': field.id,
                    'value': value,
                })
        return True

    @api.multi
    def recreate_chart_of_account(self):
        self.ensure_one()
        # TODO clean or use existing module
        # we copy reset function from account_reset_chart and call it only
        # for accounts
        from_companies = self.search([
            ('id', 'child_of', self.id),
            ('consolidation_company', '=', False),
        ])
        self._remove_accounts()
        self._recreate_chart_of_account(from_companies)
        self._recreate_properties(from_companies)

    @api.one
    def _recreate_chart_of_account(self, from_companies):
        _logger.info('Creating parent consolidated chart of account')
        if not self.consolidation_company:
            raise Warning(_('Company must be of type "consolidated"'))
        account_chart_account = self.env['account.account'].create({
            'name': self.name,
            'code': '0',
            'type': 'view',
            'company_id': self.id,
            'user_type': self.env.ref('account.data_account_type_view').id,
        })
        for child_company in from_companies:
            # recorremos el plan de cuentas de la cia hija
            for child_c_account in self.env['account.account'].search([
                    ('company_id', '=', child_company.id),
                    ('parent_id', '!=', False)]):
                parent_c_account = self.env['account.account'].search([
                    ('code', '=', child_c_account.code),
                    ('company_id', '=', self.id)], limit=1)
                # si ya existe cuenta con mismo codigo en cia padre
                if parent_c_account:
                    # si la cuenta es vista, como ya haya una continuamos
                    # y no la asignamos como hija consol
                    if child_c_account.type == 'view':
                        continue
                    # verificamos si el nombre es el mismo
                    # no imprimimos el nombre del padre porque al estar
                    # en cache nos da error
                    if parent_c_account.name != child_c_account.name:
                        raise Warning(_(
                            'El código (%s) de la cuenta "%s" de la compania '
                            '"%s" ya existe en la compañía padre pero no tiene'
                            ' el mismo nombre') % (
                                child_c_account.code,
                                child_c_account.name,
                                child_company.name))
                    # si el nombre es igual la agregamos como hijas consol
                    else:
                        parent_c_account.write({
                            'child_consol_ids': [
                                (4, child_c_account.id, False)],
                        })
                # si todavía no existe cuenta con ese codigo, la creamos
                else:
                    # si la cuenta padre es la root, entonces lo ligamos a
                    # la root que creamos nosotros
                    if not child_c_account.parent_id.parent_id:
                        parent_c_parent_account = account_chart_account
                    else:
                        parent_c_parent_account = parent_c_account.search([
                            ('company_id', '=', self.id),
                            ('code', '=', child_c_account.parent_id.code)],
                            limit=1)
                        if not parent_c_parent_account:
                            raise Warning(_(
                                'No encontramos una cuenta padre para la '
                                'cuenta "%s-%s" en el plan de cuentas de la '
                                'compania padre') % (
                                    child_c_account.code,
                                    child_c_account.name))

                    # si la cuenta es vista, setamos vista
                    if child_c_account.type == 'view':
                        parent_type = 'view'
                        child_consol = False
                    else:
                        parent_type = 'consolidation'
                        child_consol = [(4, child_c_account.id, False)]
                    parent_c_account = parent_c_account.create({
                        'name': child_c_account.name,
                        'code': child_c_account.code,
                        'type': parent_type,
                        'company_id': self.id,
                        'user_type': child_c_account.user_type.id,
                        'parent_id': parent_c_parent_account.id,
                        'child_consol_ids': child_consol,
                    })

    @api.one
    # def reset_chart(self):
    def _remove_accounts(self):
        """
        This method removes the chart of account on the company record,
        including all the related financial transactions.
        """
        logger = logging.getLogger('openerp.addons.account_reset_chart')

        def unlink_from_company(model):
            logger.info('Unlinking all records of model %s for company %s',
                        model, self.name)
            try:
                obj = self.env[model].with_context(active_test=False)
            except KeyError:
                logger.info('Model %s not found', model)
                return
            self._cr.execute(
                """
                DELETE FROM ir_property ip
                USING {table} tbl
                WHERE value_reference = '{model},' || tbl.id
                    AND tbl.company_id = %s;
                """.format(model=model, table=obj._table),
                (self.id,))
            if self._cr.rowcount:
                logger.info(
                    "Unlinked %s properties that refer to records of type %s "
                    "that are linked to company %s",
                    self._cr.rowcount, model, self.name)
            records = obj.search([('company_id', '=', self.id)])
            if records:  # account_account.unlink() breaks on empty id list
                records.unlink()

        # self.env['account.journal'].search(
        #     [('company_id', '=', self.id)]).write({'update_posted': True})
        # statements = self.env['account.bank.statement'].search(
        #     [('company_id', '=', self.id)])
        # statements.button_cancel()
        # statements.unlink()

        # try:
        #     voucher_obj = self.env['account.voucher']
        #     logger.info('Unlinking vouchers.')
        #     vouchers = voucher_obj.search(
        #         [('company_id', '=', self.id),
        #          ('state', 'in', ('proforma', 'posted'))])
        #     vouchers.cancel_voucher()
        #     voucher_obj.search(
        #         [('company_id', '=', self.id)]).unlink()
        # except KeyError:
        #     pass

        # try:
        #     if self.env['payment.order']:
        #         logger.info('Unlinking payment orders.')
        #         self._cr.execute(
        #             """
        #             DELETE FROM payment_line
        #             WHERE order_id IN (
        #                 SELECT id FROM payment_order
        #                 WHERE company_id = %s);
        #             """, (self.id,))
        #         self._cr.execute(
        #             "DELETE FROM payment_order WHERE company_id = %s;",
        #             (self.id,))

        #         unlink_from_company('payment.mode')
        # except KeyError:
        #     pass

        # unlink_from_company('account.banking.account.settings')
        # unlink_from_company('res.partner.bank')

        # logger.info('Unlinking reconciliations')
        # rec_obj = self.env['account.move.reconcile']
        # rec_obj.search(
        #     [('line_id.company_id', '=', self.id)]).unlink()

        # logger.info('Reset paid invoices\'s workflows')
        # paid_invoices = self.env['account.invoice'].search(
        #     [('company_id', '=', self.id), ('state', '=', 'paid')])
        # if paid_invoices:
        #     self._cr.execute(
        #         """
        #         UPDATE wkf_instance
        #         SET state = 'active'
        #         WHERE res_type = 'account_invoice'
        #         AND res_id IN %s""", (tuple(paid_invoices.ids),))
        #     self._cr.execute(
        #         """
        #         UPDATE wkf_workitem
        #         SET act_id = (
        #             SELECT res_id FROM ir_model_data
        #             WHERE module = 'account'
        #                 AND name = 'act_open')
        #         WHERE inst_id IN (
        #             SELECT id FROM wkf_instance
        #             WHERE res_type = 'account_invoice'
        #             AND res_id IN %s)
        #         """, (tuple(paid_invoices.ids),))
        #     paid_invoices.signal_workflow('invoice_cancel')

        # inv_ids = self.env['account.invoice'].search(
        #     [('company_id', '=', self.id)]).ids
        # if inv_ids:
        #     logger.info('Unlinking invoices')
        #     self.env['account.invoice.line'].search(
        #         [('invoice_id', 'in', inv_ids)]).unlink()
        #     self.env['account.invoice.tax'].search(
        #         [('invoice_id', 'in', inv_ids)]).unlink()
        #     self._cr.execute(
        #         """
        #         DELETE FROM account_invoice
        #         WHERE id IN %s""", (tuple(inv_ids),))

        # logger.info('Unlinking moves')
        # moves = self.env['account.move'].search([('company_id', '=', self.id)])
        # if moves:
        #     self._cr.execute(
        #         """UPDATE account_move SET state = 'draft'
        #            WHERE id IN %s""", (tuple(moves.ids),))
        # moves.unlink()

        # self.env['account.fiscal.position.tax'].search(
        #     ['|', ('tax_src_id.company_id', '=', self.id),
        #      ('tax_dest_id.company_id', '=', self.id)]
        # ).unlink()
        # self.env['account.fiscal.position.account'].search(
        #     ['|', ('account_src_id.company_id', '=', self.id),
        #      ('account_dest_id.company_id', '=', self.id)]
        # ).unlink()
        # unlink_from_company('account.fiscal.position')
        # unlink_from_company('account.analytic.line')
        # unlink_from_company('account.tax')
        # unlink_from_company('account.tax.code')
        # unlink_from_company('account.journal')
        unlink_from_company('account.account')
        return True
