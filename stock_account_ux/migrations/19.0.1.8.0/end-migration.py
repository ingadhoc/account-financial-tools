import logging

from odoo.tools import SQL
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """Recompute the moves whose related invoice can change with the new criterion.

    The related invoice used to be the most recent one of the picking's orders. Now it
    is the invoice of the move's own sale or purchase line that covers the move's
    quantity, net of credit notes. The new criterion only narrows the old one, so only
    moves showing an invoice that is not their own entry can change. Among them, a move
    that goes to the customer or comes from the vendor stays as it is when that invoice
    is the only posted one of its line and the line is invoiced at least as much as it
    was delivered: that invoice covers every move of the line. The rest, picks of a
    multi-step delivery included (the compute gives them no invoice), are found in SQL
    and recomputed, so a big base does not recompute every invoiced move. In the
    end-migration so ``sale_stock`` and ``purchase_stock`` are loaded and the compute
    sees their invoices."""
    unchanged = []
    if openupgrade.column_exists(env.cr, "stock_move", "sale_line_id"):
        unchanged.append(
            SQL(
                """
                EXISTS (
                    SELECT 1
                      FROM sale_order_line line
                     WHERE line.id = move.sale_line_id
                       AND 'customer' IN (
                               SELECT location.usage
                                 FROM stock_location location
                                WHERE location.id IN (move.location_id, move.location_dest_id)
                           )
                       AND line.qty_invoiced >= line.qty_delivered
                       AND ARRAY[move.related_account_move_id] = (
                               SELECT array_agg(DISTINCT invoice.id)
                                 FROM sale_order_line_invoice_rel rel
                                 JOIN account_move_line aml ON aml.id = rel.invoice_line_id
                                 JOIN account_move invoice ON invoice.id = aml.move_id
                                WHERE rel.order_line_id = line.id
                                  AND invoice.state = 'posted'
                                  AND invoice.move_type IN ('out_invoice', 'out_refund')
                           )
                )
                """
            )
        )
    if openupgrade.column_exists(env.cr, "stock_move", "purchase_line_id"):
        unchanged.append(
            SQL(
                """
                EXISTS (
                    SELECT 1
                      FROM purchase_order_line line
                     WHERE line.id = move.purchase_line_id
                       AND 'supplier' IN (
                               SELECT location.usage
                                 FROM stock_location location
                                WHERE location.id IN (move.location_id, move.location_dest_id)
                           )
                       AND line.qty_invoiced >= line.qty_received
                       AND ARRAY[move.related_account_move_id] = (
                               SELECT array_agg(DISTINCT bill.id)
                                 FROM account_move_line aml
                                 JOIN account_move bill ON bill.id = aml.move_id
                                WHERE aml.purchase_line_id = line.id
                                  AND bill.state = 'posted'
                                  AND bill.move_type IN ('in_invoice', 'in_refund')
                           )
                )
                """
            )
        )
    if not unchanged:
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
            SQL(" OR ").join(unchanged),
        )
    )
    _logger.info("Recomputing the related invoice of %s stock moves", len(rows))
    env["stock.move"].with_context(active_test=False).browse(
        [move_id for (move_id,) in rows]
    )._recompute_related_account_move()
