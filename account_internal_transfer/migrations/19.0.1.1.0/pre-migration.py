import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Create and populate destination_company_id for existing internal transfers

    This migration creates the destination_company_id column and populates it
    for existing internal transfer payments to avoid recomputation on large databases.

    The value is taken from the paired payment's company_id when available,
    otherwise it defaults to the payment's own company_id.
    """
    _logger.info("Creating and populating destination_company_id for internal transfers")

    # Check if the column already exists
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='account_payment'
            AND column_name='destination_company_id'
    """)

    if not cr.fetchone():
        _logger.info("Creating destination_company_id column")
        # Create the column as nullable integer with foreign key to res_company
        cr.execute("""
            ALTER TABLE account_payment
            ADD COLUMN destination_company_id INTEGER
            REFERENCES res_company(id) ON DELETE SET NULL
        """)
    else:
        _logger.info("Column destination_company_id already exists, skipping creation")

    # Update destination_company_id based on paired_internal_transfer_payment_id
    # For payments that have a paired payment, use the paired payment's company
    cr.execute("""
        UPDATE account_payment ap
        SET destination_company_id = paired.company_id
        FROM account_payment paired
        WHERE ap.is_internal_transfer = TRUE
            AND ap.paired_internal_transfer_payment_id = paired.id
            AND ap.paired_internal_transfer_payment_id IS NOT NULL
    """)

    rows_updated = cr.rowcount
    _logger.info("Updated %s payments with paired transfer company", rows_updated)

    # For payments without a paired payment, set destination_company_id to their own company_id
    cr.execute("""
        UPDATE account_payment
        SET destination_company_id = company_id
        WHERE is_internal_transfer = TRUE
            AND paired_internal_transfer_payment_id IS NULL
            AND destination_company_id IS NULL
    """)

    rows_fallback = cr.rowcount
    _logger.info("Updated %s payments without paired transfer (fallback to own company)", rows_fallback)

    _logger.info("Migration completed: %s total payments updated", rows_updated + rows_fallback)
