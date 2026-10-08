import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """Resolve the related invoices of the moves the post-migration left without an entry.

    Not in the post-migration: the module only depends on ``stock_account``, so when it
    runs ``sale_stock`` and ``purchase_stock`` may not be loaded yet, and the compute
    would not see the customer invoices nor the vendor bills. The product valuation
    depends on the company, so the perpetual moves are searched one company at a time."""
    Move = env["stock.move"].with_context(active_test=False)
    for company in env["res.company"].search([]):
        moves = Move.with_company(company).search(
            [
                ("company_id", "=", company.id),
                ("related_account_move_id", "=", False),
                ("picking_id", "!=", False),
                ("product_id.valuation", "=", "real_time"),
            ]
        )
        _logger.info("Resolving the related invoices of %s moves of %s", len(moves), company.name)
        moves.with_env(Move.env)._recompute_related_account_move()
