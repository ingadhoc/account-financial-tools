import logging

from odoo.tools import split_every
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """Fill ``stock.move.related_account_move_id``, stored from this version on.

    Same precedence as the compute: the last booked value adjustment entry wins, then the
    move's own posted entry. The moves left without one can only get a related invoice,
    which needs a perpetual product and a picking: those are computed by the ORM in
    batches, as the valuation method and the related invoices are not a plain join."""
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE stock_move sm
           SET related_account_move_id = sm.account_move_id
          FROM account_move am
         WHERE am.id = sm.account_move_id
           AND am.state = 'posted'
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE stock_move sm
           SET related_account_move_id = booked.account_move_id
          FROM (
                SELECT DISTINCT ON (pv.move_id) pv.move_id, pv.account_move_id
                  FROM product_value pv
                  JOIN account_move am ON am.id = pv.account_move_id
                 WHERE pv.move_id IS NOT NULL
                   AND am.state = 'posted'
                 ORDER BY pv.move_id, pv.date DESC, pv.id DESC
               ) booked
         WHERE booked.move_id = sm.id
        """,
    )
    Move = env["stock.move"].with_context(active_test=False)
    moves = Move.search(
        [
            ("related_account_move_id", "=", False),
            ("picking_id", "!=", False),
            ("product_id.valuation", "=", "real_time"),
        ]
    )
    _logger.info("Resolving the related invoices of %s moves", len(moves))
    field = Move._fields["related_account_move_id"]
    for ids in split_every(1000, moves.ids):
        batch = Move.browse(ids)
        env.add_to_compute(field, batch)
        batch._recompute_recordset(["related_account_move_id"])
        env.flush_all()
        env.invalidate_all()
