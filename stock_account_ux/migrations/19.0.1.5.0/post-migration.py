from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Fill ``stock.move.related_account_move_id``, stored from this version on.

    Same precedence as the compute: the last booked value adjustment entry wins, then the
    move's own posted entry. The moves left without one can only get a related invoice:
    the end-migration resolves those, once ``sale_stock`` and ``purchase_stock`` are
    loaded."""
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
