.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

===============================
Account Invoice Historical Cost
===============================

``account.invoice.report`` is a SQL view: its columns are recomputed on every
query. ``price_margin`` and ``inventory_value`` are computed against the
product's *current* cost (``standard_price``), so changing a product's cost
today silently changes the margin of old, already posted invoices. This
module freezes the real cost on the invoice line so historical margin
analysis stays stable.

What it does
============

#. Adds ``historical_cost`` and ``historical_cost_provisional`` on
   ``account.move.line``. On posting a customer invoice (``out_invoice``,
   ``out_refund``, ``out_receipt``), the real cost of the delivered goods
   (COGS, FIFO/average/standard aware) is frozen on the line, using the same
   formula the core uses to build the invoice's COGS journal items. Lines
   without a valuated delivery yet are marked ``historical_cost_provisional``
   and completed automatically once the related stock move is done.
#. Overrides ``account.invoice.report`` so ``price_margin`` and
   ``inventory_value`` read the frozen cost when present, falling back to the
   current dynamic computation via ``COALESCE`` when it is not — so invoices
   posted before installing this module keep showing exactly the same
   numbers as before. Adds a derived measure ``historical_unit_cost``
   (quantity-weighted) and a search filter on whether the cost is still
   provisional.
#. Both fields are exposed as optional (hidden by default) columns on
   invoice lines / journal items lists, for auditing a specific line.

Known limitations
==================

- **Opt-in module** (not ``auto_install``): each client decides when to
  adopt this change of semantics. Without a backfill (deliberately not
  implemented), the report will show a step in the numbers at the
  installation date — old invoices keep the dynamic calculation, new ones
  get the frozen cost.
- Only sale documents are covered. ``inventory_value`` on vendor bills keeps
  moving with the product's current cost, as before.
- With periodic (non ``real_time``) valuation and partial invoicing, cost is
  allocated by weighted average of the linked deliveries rather than
  following FIFO consumption invoice by invoice. The total always
  reconciles; a single invoice's allocation may not match its exact layer
  consumption.
- A valuation adjustment made after posting does not propagate to an
  already posted invoice — same behavior as the core's COGS lines. To
  reflect it, reset the invoice to draft and post it again.
- In companies with ``real_time`` valuation, completing a provisional line
  on delivery can leave the report diverging from the already posted COGS
  journal item (which the core never corrects retroactively). This is a
  known and accepted trade-off, not a bug.

Operational note
=================

This module needs to be added by hand to runbot's "with tests" build module
whitelist before its tests can run in CI.

|company_logo|

This module is maintained by |company|.

|icon| |company|
