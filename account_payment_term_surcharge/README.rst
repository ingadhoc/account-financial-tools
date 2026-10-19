.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

===========================
Surcharges on payment terms
===========================

This module allows us to define a set of surcharge terms and then automatically create surcharge invoices through a scheduled action that runs every day. 
A debit note will automatically be created upon matching the surcharge terms.

**TODO:**

* Agregar impuestos y cuentas analiticas a las lineas de la factura de recargo


Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. In order to used please configure the surcharge product in account settings
#. Optionally, enable the automatic validation of surcharge invoices in the same settings (both options are company-specific)
#. On each payment term, add the surcharges (percentage and when it applies) in the "Surcharges" section

Usage
=====

Every day the scheduled action "Create Surcharges Invoices" looks for posted invoices that are not fully paid and whose payment term has surcharges due.
For each one it creates a debit note, linked to the original invoice, for the surcharge percentage over the amount still due.
If the debit note cannot be created, the invoice is flagged with "Avoid Surcharge Invoice" so the scheduled action skips it, and a note is posted in its chatter.
The flag is cleared when the invoice is posted again.

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
