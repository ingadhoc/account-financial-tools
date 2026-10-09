.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

==========
Account UX
==========

Several Improvements to accounting:

#. Add an option per company on accounting settings to force reconciliation on company currency (more info on tooltip/help of that setting)
#. On taxes menu allow when searching by name search also by description
#. Make subtotal included / excluded optional and not related to tax b2b/b2c
#. Add reconciliations menu on accounting (only with debug mode)
#. Add on journal items availability to search by analytic distribution
#. By default, when creating invoices manually, actual partner is choose, with this module the partner salesperson will be choosen. The same applies when an invoice is duplicated.
#. Make origin always visible on invoices. We also think is a good idea to make it editable in case you want to link a manual invoice to, for eg, a sale order
#. Adds possibility of filtering and grouping by company on invoices.
#. Add button "Delete Number" in cancelled customer invoices
#. Add maturity date on manual journal entries
#. Add internal notes on invoices (account.move) to be used later by sales / pickings
#. Add wizard to transfer accounting entries between partners. Adds the action
   "Transfer Accounting Entries" on invoices to move amounts from the
   original partner to a destination partner. Supports multiple selected
   invoices, previews the resulting journal entries and creates balanced
   transfer moves.
#. Show the "Reversal of" field always, like the origin field, not matter if the field is set or not or the type of account.move.
#. Add filter by vat in the partners list views.
#. Add ``shared_to_branches`` on ``account.journal`` to let a journal choose how far down the branch tree it can be used.
#. Show a warning on sale/purchase journals when the company has no VAT number configured and the journal uses Latin American documents (``l10n_latam_use_documents``). This alert helps detect misconfigured journals that may cause issues with document sequencing.
#. When registering a payment from an invoice of another company of the same branch
   tree, book the payment in the company the user is standing on whenever the whole
   debt is the same legal entity as that company. Odoo always takes the company out of
   the debt (the shallowest company of the lines, or the root one for sibling
   companies), so paying from a branch handed the payment to the parent. In that case
   the wizard offers, and picks by default, the journals the paying company can use (its
   own first), so a parent journal not shared to the branch is never proposed. For a debt
   of another legal entity nothing changes: the company of the debt travels, and the
   field stays readonly in both cases.
#. Let an entry line be used anywhere inside its legal entity, and not only in the
   company that owns it (``account.move.line._check_company_domain``). Odoo's default for
   this model is the strict one and it is symmetric, so a payment of a branch could not
   settle a debt of its parent nor the other way round. Lines of a company of **another**
   legal entity stay out, which is the guarantee that is kept.
#. Add a single criterion for "which companies are the same legal entity" inside a
   branch hierarchy, as the stored and indexed field ``legal_entity_root_id`` on
   ``res.company``, plus the method ``_get_legal_entity_companies()``:

   * Two companies are the same legal entity only when they **explicitly declare the
     same VAT number** and every company in the chain between them declares it too.
   * A company with an empty VAT number, or with ``/``, is **always its own legal
     entity**: it never takes its parent's VAT number. This diverges on purpose from
     the native criterion of ``account_reports``
     (``res.company._get_branches_with_same_vat``), which considers an empty VAT
     number to be the same as the closest parent's one and therefore includes
     auxiliary companies in the parent's tax reports and returns.
   * A VAT number cannot reappear below a break in the chain (parent ``123`` / branch
     without VAT number / sub-branch ``123`` is rejected), so that "same legal entity"
     never depends on how deep in the hierarchy you look.

   The field is stored so the criterion can be used where the VAT number itself cannot:
   record rules and report filters. ``account_accountant_ux`` is the module that
   plugs it into the reports of ``account_reports``.
#. Delegate the accounting policy of a legal entity to the head of that entity instead of
   to the root company, as a second tier of the delegation core does
   (``res.company._get_legal_entity_delegated_field_names``). The tier holds
   ``fiscalyear_last_day``, ``fiscalyear_last_month``, ``account_storno`` and
   ``tax_exigibility`` — the year the entity closes and files with, whether it reverses
   with storno accounting and whether it uses cash basis, all three decided by whoever
   signs the return. Inside a legal entity the value is still shared and still enforced,
   with the same five mechanisms core uses —the onchange, the copy on ``create``, the
   propagation on ``write``, a constraint and readonly in the view— but the comparison
   stops at the boundary of the entity, so a company that heads its own one is free and
   becomes the reference for its own subtree. Declaring the parent's VAT number on a
   company that closes its year on another date is rejected, so an entity never disagrees
   with itself.

   ``currency_id`` is the only field left delegated to the root, and on purpose: under
   branches the currency —and with it the chart of accounts and the stock valuation— is
   meant to be identical across the whole tree, whatever the VAT number says.

   What this does **not** do, so nobody reads more into it: it makes these *settable* per
   legal entity, and nothing else. Two things still break with uneven fiscal years, and
   each one is its own development — the lock dates, which core resolves by walking the
   whole chain of parents and taking the maximum (closing at the root still blocks a
   branch, and the hard lock admits no exception), and the general ledger's cut of the
   year result, which uses a single date for every selected company and therefore gives a
   wrong number with no error. ``account_accountant_ux`` carries the other half of the
   change, the one that needs Enterprise: who may declare an explicit
   ``account.fiscal.year`` and who reads it.
#. Turn "is this record shared to the branches?" into "how far does it reach?", as the
   ``shared.to.branches.mixin`` abstract model, so that every model that shares records down a
   branch tree answers it the same way. The field ``shared_to_branches`` has three values:

   * **All branches**: every company below this one, whatever its VAT number. This is what
     the mechanism did before, so it is the value every existing record is migrated to.
   * **Same legal entity**: only the branches that are the same legal entity, resolved with
     ``legal_entity_root_id`` above. An auxiliary company with no VAT number of its own is a
     different legal entity and is left out.
   * **Not shared**: only the company that owns the record.

   The mixin gives the field, a Python check (``_is_shared_to_company``) and a domain
   (``_shared_to_branches_domain``) whose terms are all indexed columns, so the scope can be
   resolved in a record rule too. What it does **not** decide is the default per model nor
   where the scope is applied, because neither is the same everywhere:

   * On ``account.journal`` it is applied on the company domain and on the access rule
     ``account.journal_comp_rule`` (``ir.access``), and the value follows the journal type as before
     (miscellaneous and purchase journals are shared, the rest are not).
   * On ``account.fiscal.position`` it is applied on the **autodetection**
     (``_get_fpos_validation_functions``) and not on the company domain: narrowing the domain
     would make every document that already references the parent's position fail its company
     check. So the position stays selectable by hand and keeps working in the company that owns
     it — only the automatic match is scoped. New positions reach all branches.
#. This replace original odoo wizard for changing currency on an invoice with serveral improvements:

   * Preview and allow to change the rate thats is going to be used.
   * Log the currency change on the chatter.
   * Add this functionality to supplier invoices.
   * Change currency wizard only works when multi currency is activated
   * The change button is shown on draft invoices to users of the multi currency group
   * We can restrict the change of the currency for a group of users by adding them to "Restrict Change Invoice Currency Exchange" group

#. Add amount_total and amount_untaxed in the invoice tree view as optional and hide fields
#. Make Debit Note Origin field visible and editable by the user in the account.move form view. This will help to link new debit notes with the original invoice when this ones were not created from invoices "Add Debit Note" action button directly.
#. Add field 'memo' in view_account_payment_tree.
#. On payments, fix the use case where a journal is only suitable for one kind of operation (lets said inbound) and it is selected but then the user selects "outbound" type. Without this fix, the journals remains selected
#. Upgraded Invoice Analysis report, tree view added and new fields
#. Hide the chart template reload button and the Sale Receipts setting in accounting settings
#. Add several imrpovements on payment report:
   * Display table of debt being cancelled only if there is debt being cancelled
   * When all invoices being paid are of a second currency and the same currency, hide a column that doesn´t add value
   * Not yet improved, if you paid invoices of different currencies the report is not so good. This is not improved yet as it is not a common use case
#. Add tracking to fiscal position field on invoices so changes are logged in the chatter
#. Changing the fiscal position of an invoice recomputes the taxes of its lines.
#. Send the customer invoice by email when it is posted, if its journal has an email template
   (also from the mass confirmation and from background posting, where the sending is left to
   the native sending cron). A partner without email, or an error rendering the document, is
   logged on the chatter instead of blocking the posting. The invoice and credit note email
   templates attach the invoice report.
#. Show the invoice currency rate as "1 currency = X company currency", editable while the
   invoice is a draft with a date; every change is logged on the chatter and a zero rate is
   rejected. Invoices without date show an alert, and their rate is refreshed when posted.
#. When an invoice has no payment term, its due date cannot be earlier than the invoice date.
#. On customer invoices the accounting date must be the same as the invoice date.
#. Check the company consistency of the lines (taxes and accounts included) when posting.
#. Duplicating an invoice drops the archived taxes of its lines.
#. Payments: a posted payment cannot be deleted (it has to be reset to draft first), and
   confirming a payment whose journal entry was deleted regenerates it.
#. Journals: the suspense account cannot be one of the outstanding accounts of the journal
   payment methods (checked from both sides), credit card journals get their own default
   account, the payment sequence is disabled by default, and journals of the branch the user
   is standing on are listed first.
#. The computation fields of a tax (amount, type, price included, base) cannot be changed once
   it has journal items.
#. A currency rate without company is rejected when there are already rates with company for
   that currency.
#. Add ``is_monetary`` on accounts, computed from the account type and editable.
#. Add Customers Ledger and Vendors Ledger menus with the open receivable and payable items.
#. The exchange difference entry of a payment is dated as the payment.
#. Create the batch payment sequence of a company when it has none (using the core method).
#. Block the manual edition of the currency rounding factor (``res.currency.rounding``), which breaks the
   accounting amounts already computed with the previous value. The block can be lifted with the system
   parameter ``account_ux.allow_currency_rounding_edit``, which the
   module creates set to ``False`` so it is visible on the system parameters list. While the parameter is
   disabled the field is shown read-only on the currency form, and the block is also enforced on write.
   Creating currencies and the rounding coming from the modules data (install / update) are not affected.

Installation
============

To install this module, you need to:

#. Just install this module.

Configuration
=============

To configure this module, you need to:

#. To ensure the 'reconcile on company currency' option previews the outstanding payments with the invoice rate, you will need to apply this FIX from https://github.com/odoo/odoo/pull/292530.

Usage
=====

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/account-financial-tools/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* |company| |icon|

Contributors
------------

Maintainer
----------

|company_logo|

This module is maintained by the |company|.

To contribute to this module, please visit https://www.adhoc.com.ar.
