##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api
from collections import OrderedDict
from odoo.addons import decimal_precision as dp
# from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    report_price_unit = fields.Float(
        compute='_compute_report_prices_and_taxes',
        digits=dp.get_precision('Report Product Price'),
    )
    report_price_subtotal = fields.Monetary(
        compute='_compute_report_prices_and_taxes'
    )
    report_price_net = fields.Float(
        compute='_compute_report_prices_and_taxes',
        digits=dp.get_precision('Report Product Price'),
    )
    report_invoice_line_tax_ids = fields.One2many(
        compute="_compute_report_prices_and_taxes",
        comodel_name='account.tax',
    )

    @api.multi
    @api.depends('price_unit', 'price_subtotal', 'invoice_id.document_type_id')
    def _compute_report_prices_and_taxes(self):
        for line in self:
            invoice = line.invoice_id
            taxes_included = (
                invoice.document_type_id and
                invoice.document_type_id.get_taxes_included() or False)
            if not taxes_included:
                price_unit = line.invoice_line_tax_ids.with_context(
                    round=False).compute_all(
                        line.price_unit, invoice.currency_id, 1.0,
                        line.product_id, invoice.partner_id)
                report_price_unit = price_unit['total_excluded']
                report_price_subtotal = line.price_subtotal
                not_included_taxes = line.invoice_line_tax_ids
                report_price_net = report_price_unit * (
                    1 - (line.discount or 0.0) / 100.0)
            else:
                included_taxes = line.invoice_line_tax_ids.filtered(
                    lambda x: x in taxes_included)
                not_included_taxes = (
                    line.invoice_line_tax_ids - included_taxes)
                report_price_unit = included_taxes.with_context(
                    round=False).compute_all(
                        line.price_unit, invoice.currency_id, 1.0,
                        line.product_id, invoice.partner_id)['total_included']
                report_price_net = report_price_unit * (
                    1 - (line.discount or 0.0) / 100.0)
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                report_price_subtotal = included_taxes.compute_all(
                    price, invoice.currency_id, line.quantity,
                    line.product_id, invoice.partner_id)['total_included']

            line.report_price_subtotal = report_price_subtotal
            line.report_price_unit = report_price_unit
            line.report_price_net = report_price_net
            line.report_invoice_line_tax_ids = not_included_taxes

    # TODO remove on v13
    def _get_onchange_create(self):
        return OrderedDict(
            [('_onchange_product_id',
              ['account_id', 'name', 'price_unit', 'uom_id',
               'invoice_line_tax_ids'])])

    # TODO remove on v13
    @api.model_create_multi
    def create(self, vals_list):
        """ add missing values on ail creation """

        onchanges = self._get_onchange_create()
        for onchange_method, changed_fields in onchanges.items():
            for vals in vals_list:
                if any(f not in vals for f in changed_fields):
                    line = self.new(vals)
                    getattr(line, onchange_method)()
                    for field in changed_fields:
                        if field not in vals and line[field]:
                            vals[field] = line._fields[field].convert_to_write(
                                line[field], line)

        return super().create(vals_list)
