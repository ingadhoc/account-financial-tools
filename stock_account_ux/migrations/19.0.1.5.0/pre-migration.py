from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Create the column of ``stock.move.related_account_move_id`` before the ORM sees
    it: a new stored computed column is otherwise computed on every existing move at
    update time, in Python. The post-migration fills it instead."""
    openupgrade.logged_query(
        env.cr,
        "ALTER TABLE stock_move ADD COLUMN IF NOT EXISTS related_account_move_id int4",
    )
