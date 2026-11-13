from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Set the batch payment sequence on companies that have none.

    Core creates it on company creation and on ``account`` install, so a company that reaches an
    update without it keeps it empty and crashes when paying several customer invoices at once.
    `get_next_batch_payment_communication` creates it on demand, but backfill it here so the data
    is consistent without waiting for someone to hit the wizard.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].with_context(active_test=False).search([("batch_payment_sequence_id", "=", False)])
    companies._create_batch_payment_sequence()
