from odoo import models

from ..report.stock_valuation_report import INCLUDE_ARCHIVED_QTY_CTX


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _search_product_quantity(self, operator, value, field):
        """The standard search by quantity only looks at active products, even when the
        domain names ``active``. The valuation report keeps archived products in scope,
        so an archived product with stock has to match too."""
        if self.env.context.get(INCLUDE_ARCHIVED_QTY_CTX):
            self = self.with_context(active_test=False)
        return super()._search_product_quantity(operator, value, field)
