# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, _
from openerp.addons.account.account_invoice import account_invoice
from openerp.exceptions import RedirectWarning, except_orm
# from openerp.exceptions import except_orm, Warning, RedirectWarning

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale_refund',
    'in_refund': 'purchase_refund',
}


# onchange_partner_id_original = account_invoice.onchange_partner_id


@api.multi
def onchange_partner_id(
        self, type, partner_id, date_invoice=False,
        payment_term=False, partner_bank_id=False, company_id=False):
    """
    Solves this issue https://github.com/odoo/odoo/issues/2255
    We overwrite the function and not call by super because super function
    can raise an error
    """
    account_id = False
    payment_term_id = False
    fiscal_position = False
    bank_id = False

    if partner_id:
        p = self.env['res.partner'].browse(partner_id)
        rec_account = p.property_account_receivable
        pay_account = p.property_account_payable
        if company_id:
            if p.property_account_receivable.company_id and \
                    p.property_account_receivable.company_id.id != company_id and \
                    p.property_account_payable.company_id and \
                    p.property_account_payable.company_id.id != company_id:
                prop = self.env['ir.property']
                rec_dom = [('name', '=', 'property_account_receivable'), ('company_id', '=', company_id)]
                pay_dom = [('name', '=', 'property_account_payable'), ('company_id', '=', company_id)]
                res_dom = [('res_id', '=', 'res.partner,%s' % partner_id)]
                no_res_dom = [('res_id', '=', False)]
                rec_prop = prop.search(
                    rec_dom + res_dom) or prop.search(rec_dom + no_res_dom)
                pay_prop = prop.search(
                    pay_dom + res_dom) or prop.search(pay_dom + no_res_dom)                    
                rec_account = rec_prop.get_by_record(rec_prop)
                pay_account = pay_prop.get_by_record(pay_prop)
                if not rec_account and not pay_account:
                    action = self.env.ref('account.action_account_config')
                    msg = _('Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                    raise RedirectWarning(msg, action.id, _('Go to the configuration panel'))

        if type in ('out_invoice', 'out_refund'):
            account_id = rec_account.id
            payment_term_id = p.property_payment_term.id
        else:
            account_id = pay_account.id
            payment_term_id = p.property_supplier_payment_term.id
        fiscal_position = p.property_account_position.id
        bank_id = p.bank_ids and p.bank_ids[0].id or False

    result = {'value': {
        'account_id': account_id,
        'payment_term': payment_term_id,
        'fiscal_position': fiscal_position,
    }}

    if type in ('in_invoice', 'in_refund'):
        result['value']['partner_bank_id'] = bank_id

    if payment_term != payment_term_id:
        if payment_term_id:
            to_update = self.onchange_payment_term_date_invoice(payment_term_id, date_invoice)
            result['value'].update(to_update.get('value', {}))
        else:
            result['value']['date_due'] = False

    if partner_bank_id != bank_id:
        to_update = self.onchange_partner_bank(bank_id)
        result['value'].update(to_update.get('value', {}))

    return result

account_invoice.onchange_partner_id = onchange_partner_id


@api.multi
def onchange_company_id(
        self, company_id, part_id, type, invoice_line, currency_id):
    """
    Solves this issue https://github.com/odoo/odoo/issues/2255
    We overwrite the function and not call by super because super function
    can raise an error
    """
    # TODO: add the missing context parameter when forward-porting in trunk
    # so we can remove this hack!
    self = self.with_context(self.env['res.users'].context_get())

    values = {}
    domain = {}

    if company_id and part_id and type:
        p = self.env['res.partner'].browse(part_id)
        if p.property_account_payable and p.property_account_receivable and \
                p.property_account_payable.company_id.id != company_id and \
                p.property_account_receivable.company_id.id != company_id:
            prop = self.env['ir.property']
            rec_dom = [
                ('name', '=', 'property_account_receivable'), ('company_id', '=', company_id)]
            pay_dom = [
                ('name', '=', 'property_account_payable'), ('company_id', '=', company_id)]
            res_dom = [('res_id', '=', 'res.partner,%s' % part_id)]
            no_res_dom = [('res_id', '=', False)]
            rec_prop = prop.search(
                rec_dom + res_dom) or prop.search(rec_dom + no_res_dom)
            pay_prop = prop.search(
                pay_dom + res_dom) or prop.search(pay_dom + no_res_dom)
            rec_account = rec_prop.get_by_record(rec_prop)
            pay_account = pay_prop.get_by_record(pay_prop)
            if not rec_account and not pay_account:
                action = self.env.ref('account.action_account_config')
                msg = _(
                    'Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                raise RedirectWarning(
                    msg, action.id, _('Go to the configuration panel'))

            if type in ('out_invoice', 'out_refund'):
                acc_id = rec_account.id
            else:
                acc_id = pay_account.id
            values = {'account_id': acc_id}

        if self:
            if company_id:
                for line in self.invoice_line:
                    if not line.account_id:
                        continue
                    if line.account_id.company_id.id == company_id:
                        continue
                    accounts = self.env['account.account'].search(
                        [('name', '=', line.account_id.name), ('company_id', '=', company_id)])
                    if not accounts:
                        action = self.env.ref(
                            'account.action_account_config')
                        msg = _(
                            'Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                        raise RedirectWarning(
                            msg, action.id, _('Go to the configuration panel'))
                    line.write({'account_id': accounts[-1].id})
        else:
            for line_cmd in invoice_line or []:
                if len(line_cmd) >= 3 and isinstance(line_cmd[2], dict):
                    line = self.env['account.account'].browse(
                        line_cmd[2]['account_id'])
                    if line.company_id.id != company_id:
                        raise except_orm(
                            _('Configuration Error!'),
                            _(
                                "Invoice line account's company and invoice's company does not match.")
                        )

    if company_id and type:
        journal_type = TYPE2JOURNAL[type]
        journals = self.env['account.journal'].search(
            [('type', '=', journal_type), ('company_id', '=', company_id)])
        if journals:
            values['journal_id'] = journals[0].id
        journal_defaults = self.env['ir.values'].get_defaults_dict(
            'account.invoice', 'type=%s' % type)
        if 'journal_id' in journal_defaults:
            values['journal_id'] = journal_defaults['journal_id']
        if not values.get('journal_id'):
            field_desc = journals.fields_get(['type'])
            type_label = next(
                t for t, label in field_desc['type']['selection'] if t == journal_type)
            action = self.env.ref('account.action_account_journal_form')
            msg = _(
                'Cannot find any account journal of type "%s" for this company, You should create one.\n Please go to Journal Configuration') % type_label
            raise RedirectWarning(
                msg, action.id, _('Go to the configuration panel'))
        domain = {'journal_id':  [('id', 'in', journals.ids)]}

    return {'value': values, 'domain': domain}

account_invoice.onchange_company_id = onchange_company_id
