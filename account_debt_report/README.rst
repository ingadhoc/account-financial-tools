.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3


=======================
Account Debt Management
=======================

It adds new report to see partner debt:

* IMPORTANT: for users without invoicing rights, we still allow to get the receivable debt report for any customer (not only the ones for the user)
* You can send email to one or multiple partners with they debt report

Installation
============

To install this module, you need to:

#. Just install this module

Configuration
=============

To configure this module, you need to: TODO add config to set parameter

Usage
=====

To use this module, you need to:

#. Go to partners
#. From one partner o sellecting multiple ones, choose "Print / Account Debt Report"

Filtering by currency
---------------------

The "Company Currency" and "Secondary Currency" checks of the wizard select which items
get into the report, and which amount columns are printed. Both come checked by default:

* **Both checked (default)**: the consolidated report. Every item, the ones issued in a
  foreign currency converted to the company currency along with their original amount,
  exchange rate differences included.
* **Company currency only**: only the items issued in the company currency. Items issued
  in other currencies are left out entirely, not converted.
* **Secondary currency only**: only the items issued in a currency other than the company
  one, expressed in their own currency.

This lets a customer that carries debt for the same partner in two currencies send a
separate account statement per currency.

Two consequences worth knowing:

* **The individual views do not tie to the general ledger.** When a partner has items in
  more than one currency, the company currency view leaves the foreign ones out, so its
  balance will not match the general ledger of the receivable/payable account. The
  consolidated report is the one that reconciles.
* **Exchange rate differences follow the currency they were booked in.** They are born
  reconciled, so they only ever show up with "Full history" checked. Odoo books the
  difference on whichever side of the reconciliation is settled in the reconciliation
  currency but still carries a residual in company currency, and that side depends on
  both which document is foreign and the direction the rate moved. So a difference can
  end up in the foreign currency, where the filter leaves it out of both individual
  views, or in the company currency, where it does show — including for a document
  issued in a foreign currency and collected in company currency, whose own document is
  not in that view. Filtering by currency cannot avoid the second case.

Each item is compared against the currency of its own company, so the filter stays exact
when the report spans several companies with different currencies.

**Companies reconciling on their own currency are left out of the filter**, and keep the
behaviour they had before it existed: their items always come through and the checks only
pick columns. Those companies book the exchange difference of a foreign document as a
separate debit note in the company currency, so filtering would leave that note in without
the document it adjusts and the balance would come out wrong. The setting lives in
``account_ux``; without that module installed nothing is left out.

When a partner carries debt in more than one foreign currency, the secondary currency
columns add those amounts together, since the report has a single column pair for them.
The amount is left without a currency label in that case.

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
