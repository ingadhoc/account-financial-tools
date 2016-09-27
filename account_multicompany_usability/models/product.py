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
        company_props = self.env['res.company.property'].with_context(
            active_model='product.template', active_id=self.id)
        self.property_account_income_ids = company_props.with_context(
            property_field='property_account_income')._get_companies()
        self.property_account_expense_ids = company_props.with_context(
            property_field='property_account_expense')._get_companies()

    @api.multi
    def action_company_properties(self):
        self.ensure_one()
        return self.env['res.company.property'].with_context(
            active_model='product.template', active_id=self.id
        ).action_company_properties()


class ProductProduct(models.Model):
    """Overwrite of computed fields using product_tmpl_id instead of id"""

    _inherit = 'product.product'

    def _get_property_context(property_field):
        return (
            "{'active_model': 'product.template', "
            "'active_id': product_tmpl_id, "
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
        company_props = self.env['res.company.property'].with_context(
            active_model='product.template', active_id=self.product_tmpl_id.id)
        self.property_account_income_ids = company_props.with_context(
            property_field='property_account_income')._get_companies()
        self.property_account_expense_ids = company_props.with_context(
            property_field='property_account_expense')._get_companies()

    @api.multi
    def action_company_properties(self):
        self.ensure_one()
        return self.env['res.company.property'].with_context(
            active_model='product.template', active_id=self.product_tmpl_id.id
        ).action_company_properties()


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
        company_props = self.env['res.company.property'].with_context(
            active_model=self._name, active_id=self.id)
        self.property_account_income_categ_ids = company_props.with_context(
            property_field='property_account_income_categ')._get_companies()
        self.property_account_expense_categ_ids = company_props.with_context(
            property_field='property_account_expense_categ')._get_companies()

    @api.multi
    def action_company_properties(self):
        self.ensure_one()
        return self.env['res.company.property'].with_context(
            active_model=self._name, active_id=self.id
        ).action_company_properties()
