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

#. On invoice validation check that use hasn't delete any "automatic" tax from invoice
#. Add reconciliations menu on accounting (only with debug mode)
#. When creatin banks from bank menu, use bank name + account number for journal name (by default only account number is used). And also allow user to change this value (by default user can't)
#. Make company id not required and false by default on payment term. This field was added on v9 and it is not used anywhere
#. Add debit and credit card payment methods
#. For inbound debit and credit payments, allow to configure days for collection. This will be used to set maturity date of related journal entries
#. Add online payment method on journals
#. Add link between payment acquirer and journals
#. On payments cancelation clean "move_name" field to allow unlink of payments (TODO, this could be parametrizable)
#. Fix the balance of the "journals" in the accounting table, so that it shows the value of the column "to pay" not "total" as it does until now.
#. On cancelling reconciliation from statement lines, clean move_name to allow reconciling with new line.
#. Add send email button on bank statement lines to confirm payment to customers.
#. Add journal items menu item menu on reports with tree, grahp and pivot views (no debug mode required)
#. Add on move lines a button to open related documents
#. Add on move lines a related field to account type and allow to search and group by this field
#. On journal entries make date_maturity always visible on the journal items
#. Add a button on statemens (only with on dev mode) to cancell all statement lines
#. Add on journal items availability to search and group by analytic account and to search by analytic tags
#. Add button to cancel paid invoices that don't have related payments. This happends, for eg, if invoice amount is zero or if counterpart account is no receivable or payable.
#. Add by default, when creating invoices manually, actual partner is choose, with this module the partner salesperson will be choosen. It also choose the salesperson when creating invoices from stock.picking
#. Make origin always visible on invoices. By default odoo only make it visible when it has a value. The issue is that a user can delete the value but can't restore it again. We also think is a good idea to make it editable in case you want to link a manual invoice to, for eg, a sale order
#. Agregamos opción para que al cancelar conciliaciones con asiento de ajuste de diferencia de cambio, este último, en vez de revertirse, se borre. Esto además permite desconciliar en casos donde por defecto no se pueda (esto es un bug). Para activar este borrado se debe crear parámetro "delete_exchange_rate_entry" con valor "True"
#. Adds possibility of filtering and grouping by company on invoices.
#. Add the field "last time entries checked" with tecnical features in partner view.
#. Add option to show invoice reference field on tree view and on main section of form view.
#. Adds a wizard to add manual taxes on invoices without. Needing such taxes to be added in each of the invoice lines.
#. Add options on accounts and account types to make analytic tags required on journal entries posting
#. Adds to group by journal on invoices.
#. Adds a button "Match Payments" in the customer & suppliers form view to allow to start the matching of invoices & payments for that partner.
#. Do not allow to set same Company Currency on Journals or Accounts (enforce to keep empty if that is the cases)
#. Add quick search by this/last year/month on journal entries
#. Add visible to group account invoice the field "Journal" in account invoice form.
#. This replace original odoo wizard for changing currency on an invoice with serveral improvements:

  * Preview and allow to change the rate thats is going to be used.
  * Log the currency change on the chatter.
  * Add this functionality to supplier invoices.
  * Change currency wizard only works when multi currency is activated
  * In order to see the change button in the invoice we should be added to the "Technical Settings / Show Full Accounting Features" group
  * We can restrict the change of the currency for a group of users by adding them to "Restrict Change Invoice Currency Exchange" group



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
