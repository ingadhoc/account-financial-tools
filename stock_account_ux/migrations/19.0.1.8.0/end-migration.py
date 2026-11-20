import logging

from odoo.tools import SQL
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """Recompute the moves whose related invoice does not invoice their own order line.

    The related invoice used to be the most recent one of the picking's orders, and is now
    the most recent one of the move's own sale or purchase line. When the current invoice
    does invoice that line it is also the most recent one of the line, so it stays: only
    the moves whose invoice has none of their line can change (e.g. a delivery that took a
    down payment invoice). They are found in SQL, so a big base does not recompute every
    invoiced move. In the end-migration so ``sale_stock`` and ``purchase_stock`` are
    loaded and the compute sees their invoices."""
    own_line_checks = []
    if openupgrade.column_exists(env.cr, "stock_move", "sale_line_id"):
        own_line_checks.append(
            SQL(
                """
                EXISTS (
                    SELECT 1
                      FROM sale_order_line_invoice_rel rel
                      JOIN account_move_line line ON line.id = rel.invoice_line_id
                     WHERE rel.order_line_id = move.sale_line_id
                       AND line.move_id = move.related_account_move_id
                )
                """
            )
        )
    if openupgrade.column_exists(env.cr, "stock_move", "purchase_line_id"):
        own_line_checks.append(
            SQL(
                """
                EXISTS (
                    SELECT 1
                      FROM account_move_line line
                     WHERE line.purchase_line_id = move.purchase_line_id
                       AND line.move_id = move.related_account_move_id
                )
                """
            )
        )
    if not own_line_checks:
        return
    rows = env.execute_query(
        SQL(
            """
            SELECT move.id
              FROM stock_move move
              JOIN account_move entry ON entry.id = move.related_account_move_id
             WHERE entry.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
               AND move.related_account_move_id IS DISTINCT FROM move.account_move_id
               AND NOT (%s)
            """,
            SQL(" OR ").join(own_line_checks),
        )
    )
    _logger.info("Recomputing the related invoice of %s stock moves", len(rows))
    env["stock.move"].with_context(active_test=False).browse(
        [move_id for (move_id,) in rows]
    )._recompute_related_account_move()
