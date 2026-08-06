from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    reconcile_on_company_currency = fields.Boolean(
        help="When reconciling debt with secondary currency, if the account doesn't have a currency configured, then"
        " reconcile on company currency. This will avoid all the automatic exchange rates journal entries by forcing "
        " same rate of the original document being reconcile"
    )

    def _create_batch_payment_sequence(self):
        """Sequence used for the batch payment communication, same values as the core default."""
        self.ensure_one()
        return (
            self.env["ir.sequence"]
            .sudo()
            .create(
                {
                    "name": _("Batch Payment Number Sequence"),
                    "implementation": "no_gap",
                    "padding": 5,
                    "use_date_range": True,
                    "company_id": self.id,
                    "prefix": "BATCH/%(year)s/",
                }
            )
        )

    def get_next_batch_payment_communication(self):
        """Create the batch payment sequence when the company has none.

        Core only creates it on the `batch_payment_sequence_id` default, so it is only there for
        companies created after `account` was installed. A company that predates the field (any
        database migrated from a version where it did not exist), the main company of a fresh
        database (created by `base`, before `account` adds the field) and any duplicated company
        (the field is `copy=False`) all end up with an empty value. Then this method calls
        `next_by_id()` on an empty recordset, and since `use_date_range` reads False the no-gap
        branch queries `ir_sequence` with `id=false`, crashing with
        "operator does not exist: integer = boolean".

        Only paying several customer invoices at once reaches this code: outbound payments build
        the communication from the moves references instead.
        """
        self.ensure_one()
        company_sudo = self.sudo()
        if not company_sudo.batch_payment_sequence_id:
            company_sudo.batch_payment_sequence_id = company_sudo._create_batch_payment_sequence()
        return super().get_next_batch_payment_communication()
