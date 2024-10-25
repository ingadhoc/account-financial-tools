from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_internal_transfer = fields.Boolean(string="Internal Transfer",
        readonly=False, store=True,
        tracking=True,
        compute="_compute_is_internal_transfer")

    destination_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Destination Journal',
        domain="[('type', 'in', ('bank','cash')), ('id', '!=', journal_id)]",
        check_company=True,
    )

    @api.depends('partner_id', 'journal_id', 'destination_journal_id')
    def _compute_is_internal_transfer(self):
        for payment in self:
            payment.is_internal_transfer = (not payment.partner_id\
                                           or payment.partner_id == payment.journal_id.company_id.partner_id)\
                                           and payment.destination_journal_id

    def _get_aml_default_display_name_list(self):
        values = super()._get_aml_default_display_name_list()
        values = [
            (key, _("Internal Transfer") if self.is_internal_transfer and key == 'label' else value)
            for key, value in values
        ]
        return values

    def _get_liquidity_aml_display_name_list(self):
        res = super()._get_liquidity_aml_display_name_list()
        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                return [('transfer_to', _('Transfer to %s', self.journal_id.name))]
            else: # payment.payment_type == 'outbound':
                return [('transfer_from', _('Transfer from %s', self.journal_id.name))]
        return res

    @api.depends('destination_journal_id', 'is_internal_transfer')
    def _compute_available_partner_bank_ids(self):
        super()._compute_available_partner_bank_ids()
        for pay in self:
            if pay.is_internal_transfer:
                pay.available_partner_bank_ids = pay.destination_journal_id.bank_account_id

    @api.depends('is_internal_transfer', 'destination_journal_id')
    def _compute_destination_account_id(self):
        super()._compute_destination_account_id()
        for pay in self:
            if pay.is_internal_transfer:
                pay.destination_account_id = pay.destination_journal_id.company_id.transfer_account_id

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super()._get_trigger_fields_to_synchronize()
        return res + ('is_internal_transfer',)

    def _create_paired_internal_transfer_payment(self):
        ''' When an internal transfer is posted, a paired payment is created
        with opposite payment_type and swapped journal_id & destination_journal_id.
        Both payments liquidity transfer lines are then reconciled.
        '''
        for payment in self:
            code = payment.payment_method_line_id.code
            paired_payment = payment.copy({
                'journal_id': payment.destination_journal_id.id,
                'destination_journal_id': payment.journal_id.id,
                'payment_method_line_id': payment.destination_journal_id.inbound_payment_method_line_ids.filtered(lambda x: x.code == code).id,
                'payment_type': payment.payment_type == 'outbound' and 'inbound' or 'outbound',
                'move_id': None,
                'memo': payment.memo,
                'paired_internal_transfer_payment_id': payment.id,
                'date': payment.date,
            })
            paired_payment.filtered(lambda p: not p.move_id)._generate_journal_entry()
            paired_payment.move_id._post(soft=False)
            payment.paired_internal_transfer_payment_id = paired_payment
            body = _("This payment has been created from:") + payment._get_html_link()
            paired_payment.message_post(body=body)
            body = _("A second payment has been created:") + paired_payment._get_html_link()
            payment.message_post(body=body)

            lines = (payment.move_id.line_ids + paired_payment.move_id.line_ids).filtered(
                lambda l: l.account_id == payment.destination_account_id and not l.reconciled)
            lines.reconcile()


    def action_post(self):
        super().action_post()
        self.filtered(
            lambda pay: pay.is_internal_transfer and not pay.paired_internal_transfer_payment_id
        )._create_paired_internal_transfer_payment()

    def action_open_destination_journal(self):
        ''' Redirect the user to this destination journal.
        :return:    An action on account.move.
        '''
        self.ensure_one()

        action = {
            'name': _("Destination journal"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.journal',
            'context': {'create': False},
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.destination_journal_id.id,
        }
        return action

    @api.constrains('payment_method_line_id')
    def _check_payment_method_line_id(self):
        ''' Ensure the 'payment_method_line_id' field is not null.
        Can't be done using the regular 'required=True' because the field is a computed editable stored one.
        '''
        for pay in self:
            if not pay.is_internal_transfer:
                super()._check_payment_method_line_id()
            else:
                code = pay.payment_method_line_id.code
                destination_payment_method = pay.destination_journal_id.inbound_payment_method_line_ids.filtered(lambda x: x.code == code)
                original_payment_method = pay.payment_method_line_id
                if not destination_payment_method.payment_account_id or not original_payment_method.payment_account_id:
                    raise ValidationError(_("The origin or destination payment methods do not have an outstanding account."))
