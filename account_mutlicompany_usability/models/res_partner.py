# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, fields, models
# from openerp.exceptions import Warning


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_property_context(property_field):
        return (
            "{'active_model': 'res.partner', 'active_id': id, "
            "'property_field': '%s'}" % property_field)

    property_account_receivable_ids = fields.Many2many(
        'res.company.property',
        string="Account Receivable",
        context=_get_property_context('property_account_receivable'),
        compute='_get_properties',
    )
    property_account_payable_ids = fields.Many2many(
        'res.company.property',
        string="Account Payable",
        context=_get_property_context('property_account_payable'),
        compute='_get_properties',
    )
    property_account_position_ids = fields.Many2many(
        'res.company.property',
        string="Fiscal Position",
        context=_get_property_context('property_account_position'),
        compute='_get_properties',
    )
    property_payment_term_ids = fields.Many2many(
        'res.company.property',
        string='Customer Payment Term',
        context=_get_property_context('property_payment_term'),
        compute='_get_properties',
    )
    property_supplier_payment_term_ids = fields.Many2many(
        'res.company.property',
        string='Supplier Payment Term',
        context=_get_property_context('property_supplier_payment_term'),
        compute='_get_properties',
    )
    property_product_pricelist_ids = fields.Many2many(
        'res.company.property',
        string='Sale Pricelist',
        context=_get_property_context('property_product_pricelist'),
        compute='_get_properties',
    )

    @api.one
    def _get_properties(self):
        company_properties = self.env['res.company.property']._get_companies()
        self.property_account_receivable_ids = company_properties
        self.property_account_payable_ids = company_properties
        self.property_account_position_ids = company_properties
        self.property_payment_term_ids = company_properties
        self.property_supplier_payment_term_ids = company_properties
        self.property_product_pricelist_ids = company_properties
