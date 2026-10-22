def migrate(cr, version):
    """``block_intercompany_conciliation`` stops being a boolean and becomes a scope.

    Every existing company starts in *block always*, the same as the default for new
    ones; opening it up to the tree or to the legal entity is an explicit decision per
    tree. The field comes from ``account_accountant_ux``, so the column may already exist
    before this module ever defined it.

    It has to happen before the registry loads: left alone, the ORM casts the boolean
    column to varchar by itself and leaves ``'true'`` / ``'false'`` in it, which are not
    values of the selection. Without the column, the ORM creates it with the default.
    """
    cr.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'res_company' AND column_name = 'block_intercompany_conciliation'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    if row[0] == "boolean":
        cr.execute(
            """
            ALTER TABLE res_company
            ALTER COLUMN block_intercompany_conciliation TYPE varchar
            USING 'all'
            """
        )
    else:
        cr.execute("UPDATE res_company SET block_intercompany_conciliation = 'all'")
