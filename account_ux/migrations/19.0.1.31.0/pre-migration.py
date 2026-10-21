def migrate(cr, version):
    """``block_intercompany_conciliation`` stops being a boolean and becomes a scope.

    ``True`` maps to *block always* and ``False`` (or NULL) to *don't block*, so no live
    database changes behaviour; *block between different legal entities* is an explicit
    decision per tree. The field comes from ``account_accountant_ux``, so the column may
    already exist before this module ever defined it.

    It has to happen before the registry loads: left alone, the ORM casts the boolean
    column to varchar by itself and leaves ``'true'`` / ``'false'`` in it, which are not
    values of the selection.
    """
    cr.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'res_company' AND column_name = 'block_intercompany_conciliation'
        """
    )
    row = cr.fetchone()
    if not row or row[0] != "boolean":
        return
    cr.execute(
        """
        ALTER TABLE res_company
        ALTER COLUMN block_intercompany_conciliation TYPE varchar
        USING CASE WHEN block_intercompany_conciliation THEN 'all' ELSE 'none' END
        """
    )
