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

#. Improove partner ledger usability (tree view, not report)
#. Make subtotal included / excluded optional and not related to tax b2b/b2c
#. Add reconciliations menu on accounting (only with debug mode)
#. Add on journal items availability to search and group by analytic distribution
#. By default, when creating invoices manually, actual partner is choose, with this module the partner salesperson will be choosen. It also choose the salesperson when creating invoices from stock.picking
#. Make origin always visible on invoices.  We also think is a good idea to make it editable in case you want to link a manual invoice to, for eg, a sale order
#. Adds possibility of filtering and grouping by company on invoices.
#. Add delete number in cancelled customer invoices
#. Add options on accounts to require analytic distribution on journal entries posting
#. Adds a button "Match Payments" in the customer & suppliers form view to allow to start the matching of invoices & payments for that partner.
#. Do not allow to set same Company Currency on Journals or Accounts (enforce to keep empty if that is the cases)
#. On accounts only allow to choose account groups without children groups (last group on the hierarchy).
#. Allow to set more than one default tax for sales/purchases, useful for multicompany but also for perceptions or similar tax applied together with vat's.
#. Add internal notes on invoices (account.move) to be used later by sales / pickings
#. Show the "Reversal of" field always, like the origin field, not matter if the field is set or not or the type of account.move.
#. Add filter by vat in the partners list views.
#. Allow to disable the hash in the journal to restrict entries deletion.
#. This replace original odoo wizard for changing currency on an invoice with serveral improvements:

   * Preview and allow to change the rate thats is going to be used.
   * Log the currency change on the chatter.
   * Add this functionality to supplier invoices.
   * Change currency wizard only works when multi currency is activated
   * In order to see the change button in the invoice we should be added to the "Technical Settings / Show Full Accounting Features" group
   * We can restrict the change of the currency for a group of users by adding them to "Restrict Change Invoice Currency Exchange" group

#. Add amount_total and amount_untaxed in the invoice tree view as optional and hide fields
#. Make Debit Note Origin field visible and editable by the user in the account.move form view. This will help to link new debit notes with the original invoice when this ones were not created from invoices "Add Debit Note" action button directly.

Installation
============

To install this module, you need to:

#. Just install this module.

Configuration
=============

To configure this module, you need to:

#. No configuration nedeed.

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
