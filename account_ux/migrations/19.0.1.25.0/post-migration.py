from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Set the batch payment sequence on companies that have none.

    Core creates it on the field default, so companies that predate the field keep it empty and
    crash when paying several customer invoices at once. `get_next_batch_payment_communication`
    now creates it on demand, but backfill it here so the data is consistent without waiting for
    someone to hit the wizard.
    """
    companies = (
        env["res.company"].sudo().with_context(active_test=False).search([("batch_payment_sequence_id", "=", False)])
    )
    for company in companies:
        company.batch_payment_sequence_id = company._create_batch_payment_sequence()
