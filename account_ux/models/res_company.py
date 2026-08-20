from lxml import etree
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# ``base_vat`` already uses the slash as the canonical "no valid Tax ID" value
# (``res_partner._fix_vat_number``). Here it also carries an intent: a company
# with ``/`` is explicitly declaring that it is NOT the parent's legal entity.
VAT_NOT_APPLICABLE = "/"


class ResCompany(models.Model):
    _inherit = "res.company"

    reconcile_on_company_currency = fields.Boolean(
        help="When reconciling debt with secondary currency, if the account doesn't have a currency configured, then"
        " reconcile on company currency. This will avoid all the automatic exchange rates journal entries by forcing "
        " same rate of the original document being reconcile"
    )
    legal_entity_root_id = fields.Many2one(
        "res.company",
        string="Legal Entity Head",
        compute="_compute_legal_entity_root_id",
        store=True,
        index=True,
        recursive=True,
        help="Company at the top of the branch chain that makes up this company's legal entity. Two companies "
        "are the same legal entity only when they explicitly declare the same Tax ID and every company "
        "between them declares it too; a company without a valid Tax ID is always its own legal entity. "
        "Stored and indexed on purpose: unlike the Tax ID itself, this can be used in record rules and in "
        "report filters.",
    )

    def _normalized_vat(self):
        """The Tax ID that identifies this company's legal entity, or an empty string.

        Both an empty Tax ID and ``/`` return empty, which is what makes them behave as
        "I am my own legal entity". They are not synonyms in intent —``/`` is an explicit
        declaration, an empty one is usually data nobody loaded— but neither of them ever
        joins the parent's entity.
        """
        self.ensure_one()
        vat = (self.vat or "").strip()
        return "" if vat == VAT_NOT_APPLICABLE else vat

    def _shares_legal_entity_with(self, other):
        """Whether ``self`` and ``other`` are the same legal entity, compared directly.

        Literal equality of a declared Tax ID, with no inheritance whatsoever: an empty
        Tax ID never takes the parent's one. This is where we diverge from the native
        ``_get_branches_with_same_vat``, whose docstring states that an empty Tax ID
        counts as the closest parent's one — the behaviour that puts an auxiliary company
        inside the parent's VAT book without anyone asking for it.
        """
        self.ensure_one()
        other.ensure_one()
        own_vat = self._normalized_vat()
        return bool(own_vat) and own_vat == other._normalized_vat()

    @api.depends(
        "parent_id",
        "partner_id.vat",
        "parent_id.partner_id.vat",
        "parent_id.legal_entity_root_id",
    )
    def _compute_legal_entity_root_id(self):
        """Walk up while the Tax ID keeps matching; stop at the first break.

        ``recursive=True`` does the walking: each company only looks at its parent, and
        the head propagates down the tree. The chain has to be unbroken, so with parent
        ``123`` / child without Tax ID / grandchild ``123``, the grandchild is NOT the
        parent's entity — it is its own. That configuration is rejected by
        ``_check_legal_entity_vat_chain`` anyway, precisely so that "same legal entity"
        never depends on how deep you look.
        """
        for company in self:
            parent = company.parent_id
            if parent and company._shares_legal_entity_with(parent):
                company.legal_entity_root_id = parent.legal_entity_root_id
            else:
                company.legal_entity_root_id = company

    def _get_legal_entity_companies(self, accessible_only=False):
        """The companies that make up the same legal entity as ``self``.

        This is the single criterion the whole branch scoping hangs from: reports and
        returns, our own settlement gates, and which records get shared to branches.

        :param accessible_only: exclude companies outside ``self.env.companies``.
        :return: recordset with ``self`` as its first element, same contract as the
            native ``_get_branches_with_same_vat`` (callers use it to restore the
            active company).
        """
        self.ensure_one()
        current = self.sudo()
        candidates = (
            self.env["res.company"].sudo().search([("legal_entity_root_id", "=", current.legal_entity_root_id.id)])
        )
        if accessible_only:
            candidates &= current.root_id._accessible_branches()
        return self.browse([current.id] + (candidates - current).ids)

    @api.constrains("parent_id")
    def _check_legal_entity_chain_on_hierarchy(self):
        self._check_legal_entity_vat_chain()

    def _check_legal_entity_vat_chain(self):
        """Reject a Tax ID that reappears below a break in the branch chain.

        With parent ``123`` / child without Tax ID / grandchild ``123``, "is the
        grandchild the same legal entity as the parent?" has two defensible answers, and
        no configuration should force us to pick one. So the grandchild has to declare
        either what the child declares (nothing) or something else.

        Validates the whole subtree, not just ``self``. The hierarchy itself is immutable
        —core rejects ``parent_id`` on ``write`` with "The company hierarchy cannot be
        changed" (``res_company.write``), so a branch can never be moved under a new
        parent— but the Tax ID is not: editing it on a company that already has
        descendants can introduce the clash from above.
        """
        companies = self.filtered("id")
        if not companies:
            return
        subtree = self.env["res.company"].sudo().search([("id", "child_of", companies.ids)])
        for company in subtree:
            own_vat = company._normalized_vat()
            parent = company.parent_id
            if not own_vat or not parent or company._shares_legal_entity_with(parent):
                continue
            clashing = parent.parent_ids.filtered(lambda c: c._normalized_vat() == own_vat)
            if clashing:
                raise ValidationError(
                    _(
                        "«%(company)s» declares the Tax ID %(vat)s, which is already declared higher up the "
                        "tree by «%(ancestor)s», but the chain breaks at «%(parent)s». A Tax ID cannot "
                        "reappear below a break: «%(company)s» has to declare the same as «%(parent)s» or "
                        "something other than %(vat)s.",
                        company=company.display_name,
                        vat=own_vat,
                        ancestor=clashing[0].display_name,
                        parent=parent.display_name,
                    )
                )

    # ------------------------------------------------------------------
    # Fields delegated to the head of the legal entity
    # ------------------------------------------------------------------

    def _get_legal_entity_delegated_field_names(self):
        """Fields that every company of a legal entity has to share, and nothing else.

        Second tier of the delegation core does to the root company
        (``_get_company_root_delegated_field_names``), with the same mechanics and the
        same five enforcement points —the onchange, the copy on ``create``, the
        propagation on ``write``, the constraint and the readonly in the view— except
        that the comparison against the parent only applies while the parent is the same
        legal entity. A company that heads its own entity is free, and becomes the
        reference for its own subtree.

        What lands here is the accounting policy of the legal entity: the fiscal year it
        closes and files with, whether it reverses with storno accounting and whether it
        uses cash basis. All three are decided by whoever signs the return, so two
        entities that happen to hang from the same branch tree have no reason to answer
        them the same way.

        ``currency_id`` is the only one left at the root, and on purpose: under branches
        we do want the currency —and with it the chart of accounts and the stock
        valuation— identical across the whole tree, whatever the Tax ID says.

        What this does NOT fix, so nobody reads more into it than there is: it makes
        these *settable* per legal entity, and nothing else. Two things still break with
        uneven fiscal years, each one its own development —the lock dates, which core
        resolves by walking the whole chain of parents and taking the maximum (so closing
        at the root still blocks a branch, and the hard lock admits no exception), and
        the general ledger's cut of the year result, which uses a single date for every
        selected company and therefore gives a wrong number with no error.
        """
        return [
            "fiscalyear_last_day",
            "fiscalyear_last_month",
            "account_storno",
            "tax_exigibility",
        ]

    def _get_company_root_delegated_field_names(self):
        """Move the fiscal year out of the root tier and into the legal entity tier.

        Taking the names out of this list is what turns off core's five enforcement
        points for them; the ones below put the same five back with the entity scope.
        """
        delegated_to_entity = set(self._get_legal_entity_delegated_field_names())
        return [
            fname for fname in super()._get_company_root_delegated_field_names() if fname not in delegated_to_entity
        ]

    @api.onchange("parent_id")
    def _onchange_parent_id_legal_entity_delegated_fields(self):
        """Show the parent's value as soon as a parent is picked, like core does.

        Deliberately not conditioned on sharing the legal entity: at this point of the
        form the Tax ID may not even be loaded yet, and the parent's calendar is a better
        starting point than the 12/31 default in both cases. If the company turns out to
        be its own legal entity it is free to change it afterwards; if it does not, the
        constraint would have demanded this value anyway.
        """
        if self.parent_id:
            for fname in self._get_legal_entity_delegated_field_names():
                if self[fname] != self.parent_id[fname]:
                    self[fname] = self.parent_id[fname]

    @api.model_create_multi
    def create(self, vals_list):
        """Keep the parent's value as the default of a new branch.

        Core does this for every root-delegated field (``res_company.create``) and these
        are no longer part of that list, so the copy has to be restored: a branch born
        inside its parent's legal entity has to match it —
        ``_check_legal_entity_delegated_fields`` demands it, and without the copy creating
        a branch of a company that closes in June would fail against the 12/31 default—
        and one born as its own legal entity is better off starting from its parent's
        policy, which it is free to change afterwards.
        """
        delegated_fnames = self._get_legal_entity_delegated_field_names()
        for vals in vals_list:
            if parent := self.browse(vals.get("parent_id")):
                for fname in delegated_fnames:
                    vals.setdefault(fname, self._fields[fname].convert_to_write(parent[fname], parent))
        return super().create(vals_list)

    def write(self, vals):
        """Propagate a change made on the head of a legal entity to the rest of it.

        Core propagates from the root to every branch below it; here the value travels
        only inside the legal entity, so the branches that are another entity keep
        theirs. Only a head propagates, which is also what stops the recursion: the
        companies written below are not heads, so their own ``write`` propagates nothing.
        """
        res = super().write(vals)
        changed = sorted(set(vals) & set(self._get_legal_entity_delegated_field_names()))
        if changed:
            for company in self:
                if company.legal_entity_root_id != company:
                    continue
                entity_branches = (company._get_legal_entity_companies() - company).sudo()
                if entity_branches:
                    entity_branches.write(
                        {
                            fname: self._fields[fname].convert_to_write(company[fname], entity_branches)
                            for fname in changed
                        }
                    )
        return res

    @api.constrains(lambda self: self._get_legal_entity_delegated_field_names() + ["parent_id", "legal_entity_root_id"])
    def _check_legal_entity_delegated_fields(self):
        """Demand the parent's value, but only up to the boundary of the legal entity.

        Core's constraint (``_check_root_delegated_fields``) demands it across the whole
        branch tree; stopping at the boundary is exactly what lets two legal entities
        under the same tree close their year on different days.

        ``legal_entity_root_id`` is watched, and not ``vat``: the Tax ID is a non-stored
        related field so it cannot be watched directly, but every change to it recomputes
        the stored head. That way declaring the parent's Tax ID on a company that closes
        its year on another date is rejected when it happens, instead of leaving an
        entity whose members disagree on their own fiscal year.
        """
        for company in self:
            parent = company.parent_id
            if not parent or not company._shares_legal_entity_with(parent):
                continue
            for fname in company._get_legal_entity_delegated_field_names():
                if company[fname] == parent[fname]:
                    continue
                description = self.env["ir.model.fields"]._get("res.company", fname).field_description
                raise ValidationError(
                    _(
                        "«%(company)s» and «%(parent)s» declare the same Tax ID (%(vat)s), so they are the "
                        "same legal entity and their «%(field)s» has to be the same. Either change it on "
                        "«%(parent)s», which applies it to the whole legal entity, or give «%(company)s» its "
                        "own Tax ID if it really is a different legal entity.",
                        company=company.display_name,
                        parent=parent.display_name,
                        vat=company._normalized_vat(),
                        field=description,
                    )
                )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        """Readonly inside a legal entity, instead of on every branch.

        Core marks the root-delegated fields readonly with a flat ``parent_id != False``
        (``res_company._get_view``), and the fiscal year left that list, so it needs its
        own modifier. Comparing the stored head against the record covers the three
        cases: the head of an entity stays editable, a company inside somebody else's
        entity is readonly, and a branch being created —no ``id`` yet, head already
        computed from the parent by the onchange— is readonly too.
        """
        arch, view = super()._get_view(view_id, view_type, **options)
        delegated_fnames = set(self._get_legal_entity_delegated_field_names())
        delegated_nodes = [node for node in arch.iter("field") if node.get("name") in delegated_fnames]
        if delegated_nodes:
            for node in delegated_nodes:
                node.set("readonly", "legal_entity_root_id != id")
            if not any(node.get("name") == "legal_entity_root_id" for node in arch.iter("field")):
                # The modifier is evaluated client side, so the field it reads has to be
                # in the view. Our own form view already carries it; any other view that
                # shows a delegated field gets it added here.
                delegated_nodes[0].addprevious(
                    etree.Element("field", {"name": "legal_entity_root_id", "invisible": "1"})
                )
        return arch, view

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
