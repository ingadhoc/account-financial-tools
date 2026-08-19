from openupgradelib import openupgrade

# The three tables that store the flag: the journal, plus the two mirrors that follow it
# through a stored related field.
COLUMNS = [
    ("account_journal", "shared_to_branches"),
    ("account_payment_method_line", "shared_to_branches"),
    ("account_reconcile_model", "shared_to_branches"),
]


@openupgrade.migrate()
def migrate(env, version):
    """``shared_to_branches`` stops being a boolean and becomes a scope.

    ``True`` maps to *all branches* and ``False`` (or NULL, which behaves the same today) to
    *not shared*, so no live database changes behaviour: what is shared today stays shared to
    the whole subtree, and narrowing it to *same legal entity* is an explicit decision per
    record.

    It has to happen before the registry loads. Left alone, the ORM casts the boolean column
    to varchar by itself and leaves ``'true'`` / ``'false'`` in it, which are not values of
    the selection: the field would read as garbage and every journal would fall out of the
    sharing domain.
    """
    for table, column in COLUMNS:
        if not openupgrade.column_exists(env.cr, table, column):
            continue
        env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s
            """,
            (table, column),
        )
        row = env.cr.fetchone()
        if not row or row[0] != "boolean":
            # Already converted (re-run of the migration, or a database created after the
            # change): nothing to do.
            continue
        openupgrade.logged_query(
            env.cr,
            f"""
            ALTER TABLE {table}
            ALTER COLUMN {column} TYPE varchar
            USING CASE WHEN {column} THEN 'all' ELSE 'none' END
            """,
        )
