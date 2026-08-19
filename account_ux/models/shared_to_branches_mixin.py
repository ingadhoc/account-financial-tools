##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.misc import unquote

# Which branches a record of a parent company reaches. One axis, three values, so
# that every model that shares records down a branch tree answers the question the
# same way. The vocabulary is deliberately the same as the field-level one on
# ``res.company``: *root* / *legal entity* / *own*.
SHARED_TO_BRANCHES_SELECTION = [
    ("all", "All branches"),
    ("legal_entity", "Same legal entity"),
    ("none", "Not shared"),
]


class SharedToBranchesMixin(models.AbstractModel):
    """The scope of the branches a record is shared to.

    Odoo lets a branch use its ancestors' records through
    ``check_company_domain_parent_of``: everything the parent owns is available to the
    whole subtree, with no say in the matter. That is too much for an auxiliary company
    that is a different legal entity — it ends up using the parent's journals and being
    matched by the parent's fiscal positions.

    This mixin turns "is it shared?" into "how far does it reach?", and answers *same
    legal entity* with the single criterion of ``res.company.legal_entity_root_id``, so
    that one definition serves reports, returns, closing entries and shared records alike.

    **The mixin is deliberately not uniform.** It provides the field, the vocabulary and
    the two ways of resolving it (a Python check and a domain); what it does NOT decide is
    the default per model, nor where the scope gets applied. A journal is not shared with
    the same criterion as a fiscal position, and the seam is not the same either: for
    journals it is the company domain plus the record rule, while for fiscal positions it
    is the autodetection, because narrowing their company domain would invalidate the
    documents that already reference the parent's position. Each model wires it where it
    belongs and declares its own default.

    **The default is deliberately not here.** Each model declares it, either with a
    ``default`` or with a compute of its own — a mixin-level ``default`` would be inherited
    by the fields that have a compute and would silently take its place, because a value
    that comes from ``default_get`` counts as given and skips the compute. An empty value
    reads as *not shared*, so a model that adopts this without declaring a default fails
    closed, and the records that already exist need a migration filling in the value that
    preserves what the database did before.

    Requires ``company_id`` on the model.
    """

    _name = "shared.to.branches.mixin"
    _description = "Scope of the branches a record is shared to"

    shared_to_branches = fields.Selection(
        selection=SHARED_TO_BRANCHES_SELECTION,
        string="Shared to Branches",
        help="Which branches of this company can use this record.\n\n"
        "- All branches: every company below this one, whatever its Tax ID.\n"
        "- Same legal entity: only the branches that declare the same Tax ID as this "
        "company, with no break in the chain. An auxiliary company with no Tax ID of its "
        "own is a different legal entity and is left out.\n"
        "- Not shared: only this company.",
    )
    legal_entity_root_id = fields.Many2one(
        "res.company",
        string="Legal Entity Head",
        compute="_compute_legal_entity_root_id",
        store=True,
        index=True,
        help="Head of the legal entity of the company that owns this record. Stored on the "
        "record so that the *same legal entity* scope can be resolved in a record rule "
        "against a column of this table, instead of reaching into res.company — which a "
        "branch user cannot always read.",
    )
    has_child_companies = fields.Boolean(compute="_compute_has_child_companies")

    @api.depends("company_id.legal_entity_root_id")
    def _compute_legal_entity_root_id(self):
        """Mirror of the company's entity head. Computed and not related because a related
        field cannot resolve ``company_id`` on an abstract model, which is where this lives."""
        for record in self:
            record.legal_entity_root_id = record.company_id.legal_entity_root_id

    @api.depends("company_id", "company_id.child_ids")
    def _compute_has_child_companies(self):
        """Whether the scope is worth showing at all: without branches every value is the same."""
        for record in self:
            record.has_child_companies = bool(record.company_id.child_ids)

    def _is_shared_to_company(self, company):
        """Whether ``company`` can use this record.

        The exact answer, for the code paths that have a single company at hand — company
        consistency checks and the fiscal position autodetection. It is also the reference
        for what ``_shared_to_branches_domain`` means.
        """
        self.ensure_one()
        owner = self.company_id.sudo()
        company = company.sudo()
        if not owner or owner == company:
            return True
        if owner not in company.parent_ids:
            # Not an ancestor: sharing never had anything to do with it.
            return False
        if self.shared_to_branches == "all":
            return True
        if self.shared_to_branches == "legal_entity":
            return owner.legal_entity_root_id == company.legal_entity_root_id
        return False

    @api.model
    def _shared_to_branches_domain(self, companies):
        """Records owned by ``companies``, plus what their ancestors share with them.

        Meant for ``_check_company_domain`` on the models whose seam is the company
        domain. Every term resolves to an indexed column, so it also works in a record
        rule and in a SQL domain.

        ``companies`` can be an ``unquote`` when the domain is being rendered for the web
        client. There the only thing available is the record's own ``company_id``, as text,
        so *same legal entity* cannot be resolved and is left as permissive as *all
        branches*. That is safe: what the client gets is only a dropdown filter, and both
        the record rule and the server-side company check resolve the scope exactly.
        """
        if isinstance(companies, unquote):
            symbolic = unquote(f"{companies}")
            return Domain("company_id", "in", symbolic) | Domain(
                [
                    ("company_id", "parent_of", symbolic),
                    ("shared_to_branches", "in", ["all", "legal_entity"]),
                ]
            )

        company_ids = models.to_record_ids(companies)
        if not company_ids:
            return Domain("company_id", "=", False)

        companies = self.env["res.company"].sudo().browse(company_ids)
        # The ancestors that are the same legal entity as the company asking. Resolved per
        # company and then unioned, instead of comparing entity heads globally: with two
        # companies of different entities in the same tree, a global comparison would let
        # one of them borrow the other's entity match.
        same_entity_ancestors = {
            ancestor.id
            for company in companies
            for ancestor in company.parent_ids
            if ancestor.legal_entity_root_id == company.legal_entity_root_id
        }
        return (
            Domain("company_id", "in", company_ids)
            | Domain([("company_id", "parent_of", company_ids), ("shared_to_branches", "=", "all")])
            | Domain([("company_id", "in", list(same_entity_ancestors)), ("shared_to_branches", "=", "legal_entity")])
        )
