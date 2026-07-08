from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Limpiar ``account_stock_expense_id`` en bases ya instaladas"""
    openupgrade.logged_query(
        env.cr,
        "UPDATE account_account SET account_stock_expense_id = NULL WHERE account_stock_expense_id IS NOT NULL",
    )
