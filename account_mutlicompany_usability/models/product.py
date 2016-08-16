# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, fields, models
# from openerp.exceptions import Warning


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_property_context(property_field):
        return (
            "{'active_model': 'product.template', 'active_id': id, "
            "'property_field': '%s'}" % property_field)

    property_account_income_ids = fields.Many2many(
        'res.company.property',
        string="Income Account",
        context=_get_property_context('property_account_income'),
        compute='_get_properties',
    )
    property_account_expense_ids = fields.Many2many(
        'res.company.property',
        string="Expense Account",
        context=_get_property_context('property_account_expense'),
        compute='_get_properties',
    )

    @api.one
    def _get_properties(self):
        company_properties = self.env['res.company.property']._get_companies()
        self.property_account_income_ids = company_properties
        self.property_account_expense_ids = company_properties


class ProductCategory(models.Model):
    _inherit = 'product.category'

    def _get_property_context(property_field):
        return (
            "{'active_model': 'product.category', 'active_id': id, "
            "'property_field': '%s'}" % property_field)

    property_account_income_categ_ids = fields.Many2many(
        'res.company.property',
        string="Income Account",
        context=_get_property_context('property_account_income_categ'),
        compute='_get_properties',
    )
    property_account_expense_categ_ids = fields.Many2many(
        'res.company.property',
        string="Expense Account",
        context=_get_property_context('property_account_expense_categ'),
        compute='_get_properties',
    )

    @api.one
    def _get_properties(self):
        company_properties = self.env['res.company.property']._get_companies()
        self.property_account_income_categ_ids = company_properties
        self.property_account_expense_categ_ids = company_properties
