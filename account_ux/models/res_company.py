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
                        "La compañía «%(company)s» declara el CUIT %(vat)s, que ya está declarado más "
                        "arriba en el árbol por «%(ancestor)s», pero la cadena se corta en «%(parent)s». "
                        "No puede haber un CUIT que reaparezca después de un corte: «%(company)s» tiene "
                        "que declarar lo mismo que «%(parent)s» o algo distinto de %(vat)s.",
                        company=company.display_name,
                        vat=own_vat,
                        ancestor=clashing[0].display_name,
                        parent=parent.display_name,
                    )
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
