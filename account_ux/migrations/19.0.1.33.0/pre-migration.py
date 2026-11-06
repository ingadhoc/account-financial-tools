def migrate(cr, version):
    """``block_intercompany_conciliation`` stops being a boolean and becomes a scope.

    The value is kept: the box ticked is *block always*, unticked is *don't block*, so
    nothing changes on update. Reading other branches needs a group nobody has yet.

    It has to happen before the registry loads: left alone, the ORM casts the boolean
    column to varchar by itself and leaves ``'true'`` / ``'false'`` in it, which are not
    values of the selection. The column comes from ``account_accountant_ux``: without it,
    the ORM creates it with the default.
    """
    cr.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'res_company' AND column_name = 'block_intercompany_conciliation'
        """
    )
    row = cr.fetchone()
    if row and row[0] == "boolean":
        cr.execute(
            """
            ALTER TABLE res_company
            ALTER COLUMN block_intercompany_conciliation TYPE varchar
            USING CASE WHEN block_intercompany_conciliation THEN 'all' ELSE 'none' END
            """
        )
