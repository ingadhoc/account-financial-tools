def migrate(cr, version):
    """Superseded by 19.0.1.27.0.

    This used to rewrite ``account.journal_comp_rule`` with a boolean ``shared_to_branches``
    domain. Any update that reaches this script also runs 19.0.1.27.0, which writes the final
    domain on the same record, and the boolean domain is no longer valid once the column
    becomes a selection.
    """
