from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _name = "account.fiscal.position"
    _inherit = ["account.fiscal.position", "shared.to.branches.mixin"]

    sequence = fields.Integer(default=999)
    # Reaching every branch is what a fiscal position did before this field existed, so a new
    # one keeps doing it and narrowing it to the legal entity is an explicit decision. The
    # positions that already exist get the same value from the migration.
    shared_to_branches = fields.Selection(default="all")

    def _get_fpos_validation_functions(self, partner):
        """A fiscal position of an ancestor company only autodetects where it is shared to.

        This is the case that started the whole thing: you create a fiscal position on the
        parent and it autodetects on the auxiliary company below, which is a different legal
        entity chasing a different tax situation, so it ends up applying withholdings that do
        not belong there.

        The seam is the autodetection and **not** ``_check_company_domain``, on purpose.
        ``fiscal_position_id`` is ``check_company=True`` on ``account.move`` and on
        ``sale.order``, so narrowing the company domain would make every document that
        already references the parent's position fail its company check on the next write.
        Filtering here leaves the position selectable by hand and keeps working in the
        company that owns it — only the automatic match stops.
        """
        return super()._get_fpos_validation_functions(partner) + [
            lambda fpos: fpos._is_shared_to_company(self.env.company),
        ]
