from odoo import models

from .res_company import VALUATION_PRODUCT_CTX


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _search_valuation(self, operator, value):
        """Search ``valuation`` without the product scope of the report filters.

        The standard search applies ``res.company._get_inventory_valuation_products_domain``
        to the templates, and the scope of that hook is a list of ``product.product`` ids,
        which on a template would match other records.
        """
        return super(ProductTemplate, self.with_context(**{VALUATION_PRODUCT_CTX: None}))._search_valuation(
            operator, value
        )
