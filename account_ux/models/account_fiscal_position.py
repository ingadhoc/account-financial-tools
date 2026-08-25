from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _name = "account.fiscal.position"
    _inherit = ["account.fiscal.position", "shared.to.branches.mixin"]

    sequence = fields.Integer(default=999)
    # Reaching every branch is what a fiscal position did before this field existed, so a new
    # one keeps doing it and narrowing it to the legal entity is an explicit decision. The
    # positions that already exist get the same value from the migration.
    #
    # The help is redeclared because the scope is only half of what the user needs to predict
    # what will happen: the other half is that autodetection does not pick the way people
    # expect it to, and this field is where they are looking when they ask.
    shared_to_branches = fields.Selection(
        default="all",
        help="Which branches this fiscal position is automatically detected in.\n\n"
        "- All branches: every company below this one, whatever its Tax ID.\n"
        "- Same legal entity: only the branches that declare the same Tax ID as this company, "
        "with no break in the chain. An auxiliary company with no Tax ID of its own is a "
        "different legal entity and is left out.\n"
        "- Not shared: only this company.\n\n"
        "Careful with how the automatic detection picks one, because it is not by sequence. "
        "Odoo sorts the candidates by how deep the owning company sits in the branch tree "
        "first, and only then by sequence: a position of the branch you are standing in wins "
        "over one of its parent whatever the sequences say, and the sequence only decides "
        "between positions of the same company.\n\n"
        "This scope only narrows the automatic detection. A position stays selectable by hand "
        "and keeps working in the company that owns it.",
    )

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
