# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    @api.multi
    def send_mail(self):
        template_id = self.env['ir.model.data'].get_object_reference(
            'account_usability',
            'email_template_bank_statement')[1]
        for record in self:
            ctx = {
                'statement_line': record,
                'date': datetime.strptime(
                    record.date,
                    DEFAULT_SERVER_DATE_FORMAT).strftime("%d/%m/%Y")
            }
            record.partner_id.with_context(ctx).message_post_with_template(
                template_id, notify=True, composition_mode='mass_mail')
