.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=============
Stock Move UX
=============

This module improves the inventory valuation UX in five areas:

Journal entry link on stock moves
---------------------------------

Adds a direct link to the accounting entry on stock moves reports, so users can
audit inventory valuation from the same product movement view.

* Adds the "Asiento Contable" column on Inventory > Reporting > Moves Analysis.
* Adds the same column on inventory valuation moves list.
* Uses the Odoo 19 native link between stock moves and journal entries
  (``stock.move.account_move_id`` from ``stock_account``) and, via a
  ``res.company.action_close_stock_valuation`` override, also links the periodic
  closing entry to the moves it values. This unifies perpetual and periodic
  valuation behind the computed, searchable ``stock.move.related_account_move_id``
  field and the "With/Without Journal Entry" filters.
* The link follows what the entry actually books, with **no lower date bound**: the
  closing books the *cumulative* difference (inventory value minus booked value), so
  a move an earlier closing left out — because that closing was filtered by product
  or by Movement Type — is booked by the next full closing and is linked to it,
  however old it is. Moves already booked by a posted entry keep it.

Filters on the Inventory Valuation report
------------------------------------------

Adds five optional, multi-select, combinable filters to the Inventory Valuation
report (``stock_account.stock.valuation.report``):

* **Product** and **Product Categories** (categories include their subcategories).
* **Valuation Method** (standard / FIFO / average).
* **Valuation Type** (manual/periodic or automated/perpetual).
* **Movement Type** (Stock Moves and/or Product Value), which only affects the
  Stock Variation section and is limited to *unaccounted* records.

Product, Category, Valuation Method and Valuation Type scope the three sections
(Initial Balance, Stock Variation, Ending Stock). With no filters selected the
report behaves exactly like the standard one.

**Movement Type keeps the report balanced.** It breaks the Stock Variation down by
origin, and Ending Stock is then projected as *Initial Balance + filtered
variation*: with the filter on it stops being the real state of the stock and
becomes the accounted value the stock would have if only that portion were booked
— which is exactly what the entry generated with the filter on does book. Initial
Balance is left untouched: it is the already-booked starting point, a balance with
no origin (historical entries do not record which origin they came from), not a
flow. The two projections are complementary and add up to the real state.

**The journal entry respects the active filters.** Generating the entry from the
report posts what is on screen:

* Product / Category / Method / Valuation Type → a *partial closing* limited to
  those products; the rest stays open.
* Movement Type → a closing limited to that *origin* of the variation (only the
  stock moves portion, or only the value adjustments one), leaving the other one
  pending. Both origins are complementary and add up to the full closing, and each
  entry links only the records it actually booked, so whatever stays open keeps
  showing up in the report's variation.

The valuation leg of that entry is split into **one line per product**, and each
line **names its product in the label**. The valuation account belongs to the
category, so a global entry has several lines on the same account and the label is
what tells the user which line is whose. The counterpart keeps the generic label:
it is attributed to no product.

**The filters survive the drill-down.** The report is a client action, so it is
unmounted when navigating to the detail and mounted again when coming back through
the breadcrumb, which used to reset the filters and the date. They are now exported
via the action service's ``getLocalState`` and restored before the first render.

Known limitations (by design)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Shared valuation account.** With a product filter active, Initial Balance is
  read from the journal items **attributable to those products** (``product_id``),
  so it lines up with Ending Stock —which is exact per product— and the report adds
  up: initial + variation = ending.

  For that to hold, the closing entry books **one line per product** instead of a
  single aggregated line per account (the standard books it with
  ``product_id = False``, which is why its balance could not be filtered at all).
  The split happens *inside* the valuation account: each product takes its own
  difference (inventory value minus what is already attributed to it) and whatever
  is left unattributed —the balance coming from previously aggregated closings— goes
  to a no-product line that nets it out. Amount, counterpart and account balance are
  therefore identical to the standard entry: same entry, attributed. Right after the
  closing, each product's booked balance equals its inventory value. The manual
  "Value Stock Moves" wizard groups by account **and product** for the same reason.

  A closing done with the *Movement Type* filter is attributed the same way, but
  with the contribution of **that origin** —the stock moves one is exact, since it
  comes from records that carry a product— because that entry only books a portion:
  splitting the whole pending difference there would over-attribute it.

  **The balance booked with no product is shared out, not dropped.** On a database
  closed before this version —or where an accountant posted on the valuation account
  by hand— part of the balance carries no ``product_id``. Leaving it out made the
  filtered report disagree with the unfiltered one: product by product it reported
  more left to book than there actually was, by exactly that portion, and closing
  each product in turn booked it twice. That portion is now shared out over the
  products of the account in proportion to each one's **pending gap** (its inventory
  value minus what is already booked for it, the same figure the closing books). It
  is an estimate —the journal item records no product, so there is nothing exact to
  recover— with the property that matters: the shares of any split of the account's
  products add up to 1, so filtering by every product equals not filtering.

  The weight is the pending gap rather than the plain inventory value on purpose: a
  product already booked at its inventory value has no gap left and claims nothing,
  which is what keeps a product-by-product closing from re-sharing the leftover over
  the products already closed. When the account has no pending gap at all (everything
  booked and the leftover is a balance to write off), the weight falls back to the
  count of products, which preserves the same property. The full closing still nets
  the portion out, so on a database whose closings all ran through this module there
  is nothing to share and the computation is skipped entirely.
* **Movement Type is a breakdown, and "Product Value" is the remainder.** The
  Stock Moves component adds up the ``value`` of the unaccounted moves, which is
  what the inventory is worth for the three costing methods — including standard
  cost, where a normal receipt is already valued at the standard cost and not at
  what was paid. Moves that carry a manual adjustment are left out (a
  ``product.value`` points at them) and their contribution is taken by the other
  component. "Product Value" is then the remainder, so besides the value
  adjustments it also absorbs location reclassifications and FIFO/AVCO rounding.
  Both components always add up to the native variation.

Drill-down from the report to the underlying detail
---------------------------------------------------

In v19 the report already navigates from Initial Balance, Ending Stock and
Inventory Loss, but the **Stock Variation** section — the unaccounted difference,
i.e. exactly what has to be reviewed and posted — was not clickable at all. This
adds:

* A **"three dots" menu** on each account line of Stock Variation, with the two
  origins of the difference: **Unaccounted Stock Moves** (same scope as the Stock
  Moves component: done moves inside the valued perimeter, with no entry, up to
  the report date) and **Unaccounted Value Adjustments** (the ``product.value``
  records with no entry). Both are scoped to the account of the line and honour
  the report's active filters.
* **Initial Balance** account lines now open the **General Ledger** of *that*
  account up to the report date. The General Ledger lives in ``account_reports``
  (enterprise) and is not a dependency, so it is resolved at runtime and falls
  back to the journal items list filtered by account and date.
* A **list view, search view and menu for ``product.value``** (Inventory >
  Reporting > Value Adjustments): date, product, lot, move, previous value, new
  value, delta, journal entry and description, with "Booked / Not Booked" and
  "Price Change / Move Adjustment" filters. The model previously had only the
  "Adjust Valuation" form, so the adjustments were not consultable at all.

The domains live in Python (``action_open_variation_stock_moves``,
``action_open_variation_product_values``, ``action_open_account_ledger``), so the
drill-down is covered by regular tests instead of only through the UI.

Manual valuation of selected stock moves
----------------------------------------

Periodic valuation only reaches accounting through the global closing entry: there
is no way to book *some* moves. This adds a **"Value Stock Moves"** action to the
Actions menu of the moves lists, which opens a wizard with the **draft of the
journal entry** before posting it. It is available on:

* **Valuation** (next to the native "Adjust Valuation") and **Inventory >
  Reporting > Moves Analysis** — both list ``stock.move``.
* **Inventory > Reporting > Moves History**, which lists ``stock.move.line``: the
  action resolves the moves of the selected lines (deduplicated). Since the
  valuation unit is the *move*, a move with only some of its lines selected is
  still valued in full, and the wizard says so.

The wizard:

* Journal and date are selectable (journal defaults to the company's Stock
  Journal).
* The draft is grouped by the valuation accounts defined on the products'
  categories, with the counterpart taken from the account itself
  (``account_stock_variation_id``, falling back to the company expense account) —
  the same account resolution the native closing uses.
* Each move contributes what it adds to the *valuation*
  (``stock.move._get_inventory_value``, shared with the Movement Type filter):
  incoming moves add, outgoing moves subtract.
* On post, the entry is linked to the moves, which both blocks a second valuation
  and takes them out of the report's pending variation and of the periodic
  closing's scope.
* Every line of the valuation account **names its product in the label**. The
  account belongs to the category, so an entry over moves of several products has
  several lines on it and the label is what tells them apart. The counterpart keeps
  the generic label: it is attributed to no product.
* **Moves that already have a valuation entry are left out** of the selection, to
  avoid duplicating the product's accounted value. The wizard says which ones and
  why; if none is left to value, it refuses to open.

Revaluation entry traceability
------------------------------

When the inventory variation comes from a value change (``product.value``) rather
than from a stock movement, the closing entry left no trace: ``product.value`` has
no reference to any journal entry, and the revalued ``stock.move`` keeps pointing
to its *original* valuation entry through ``account_move_id`` (a Many2one that is
already taken). There was no way to tell an adjustment that had already been
booked from one that still produces the difference shown by the report.

This module adds:

* ``product.value.account_move_id`` — the closing entry that booked the
  adjustment, set by the ``res.company.action_close_stock_valuation`` override.
  Empty means *not booked yet*, i.e. the adjustment is still part of the Stock
  Variation to be posted. Partial closings (see the filters above) only mark the
  adjustments of the products in scope.
* ``product.value.previous_value`` / ``product.value.delta`` — the value in force
  right before the adjustment, captured on ``create``, and the variation it
  introduced. The model only stores the *new* value, and ``current_value`` cannot
  be used for this: it is ``related='move_id.value'`` and ``product.value.create``
  already ran ``_set_value()`` on the move, so once saved
  ``current_value == value``. Recomputing it afterwards from the move is not an
  option either: on AVCO/FIFO the adjustment already moved the product's
  ``standard_price``, so the "computed value" would return the new one.
* ``stock.move.related_account_move_id`` now also covers the revaluation: when the
  move has a booked value adjustment, the "Journal Entry" column (and the search)
  point to *that* entry, since it is the one reflecting the move's current
  valuation. It falls back to the original entry when there is no booked
  adjustment. The original entry always stays available in the native
  ``account_move_id``.
* A "Revaluation Not Booked" filter on the moves search view, for the moves whose
  value adjustment is still pending — the difference to be posted. The
  "With/Without Journal Entry" pair cannot express this, since it looks at the
  move's current entry.
* Read access on ``product.value`` for Inventory users and Accounting (the native
  ACL only grants it to Inventory managers, which would break the columns above
  for the accountants that actually audit valuation).

Known limitations of the traceability (by design)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Price changes are not tied to a movement.** A standard-price or lot-price
  change creates a ``product.value`` with no ``move_id``: it revalues the stock on
  hand, not a specific movement, so it is traced on ``product.value`` only and the
  moves of that product keep showing their original entry.
* **One column, one entry.** A revalued move has two entries and
  ``related_account_move_id`` is a Many2one, so the column shows the revaluation
  one; use the native ``account_move_id`` to reach the original.
* **``delta`` is expressed in the same unit as ``value``**: the move total for
  move adjustments, the unit price for product/lot price changes. The model does
  not store the quantity the price change applied to, so the two cannot be
  normalized to a single unit without inventing a figure.
* **``previous_value`` only applies going forward.** Adjustments recorded before
  installing this version have no stored previous value (it cannot be
  reconstructed), so their ``delta`` equals the new value.

Installation
============

To install this module, you need to:

#. Just install this module.

Configuration
=============

No additional configuration is required.

Usage
=====

To use this module, you need to:

#. Go to Inventory > Reporting > Moves Analysis.
#. Enable the "Asiento Contable" column if it is hidden in optional fields.
#. Open any move with accounting impact and click the linked journal entry.

Applies to valuation entries generated by:

* Automatic inventory valuation flows.
* Internal transfers with accounting impact.
* Scrap operations generating accounting entries.
* Manual valuation adjustments linked to stock moves.

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
