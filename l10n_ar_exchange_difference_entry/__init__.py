from . import models
from . import wizards
import logging

_logger = logging.getLogger(__name__)


def _create_and_set_exchange_diff_product(env):
    """This hook creates a product for exchange difference
    that will be used as product in debit notes created by this module.
    """
    ar_companies = env["res.company"].search([("country_code", "=", "AR")])
    taxes = []
    for company in ar_companies:
        tax = env.ref(f"account.{company.id}_ri_tax_vat_21_ventas", raise_if_not_found=False)
        if tax:
            taxes.append(tax.id)

    product = env["product.product"].create(
        {
            "name": "Exchange Difference",
            "type": "service",
            "sale_ok": True,
            "purchase_ok": False,
            "company_id": False,
            "taxes_id": [(6, 0, taxes)],
        }
    )
    for company in ar_companies:
        company.write({"exchange_difference_product": product.id})


def _post_init_hooks(env):
    _create_and_set_exchange_diff_product(env)
