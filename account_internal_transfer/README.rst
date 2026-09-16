.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=========================
Account Internal Transfer
=========================

This module adds internal transfers between journals as a payment option:

* Internal transfer payments: a payment marked as internal transfer moves money from its journal to a destination journal, which can belong to another branch of the same company. When it is posted, a paired payment is created in the destination journal and both payments are reconciled through the transfer account of the company.
* Destination payment method: the user can choose the payment method of the destination journal. It sets the outstanding account of the paired payment, so a destination journal with several payment methods can reach any of them. By default it uses the first available payment method of the destination journal.
* Transfer receipt: internal transfers print their own receipt report.

Installation
============

To install this module, you need to:

#. Nothing to do

Configuration
=============

To configure this module, you need to:

#. Configure an outstanding account on the payment methods of the origin and destination journals.

Usage
=====

To use this module, you need to:

#. Create a payment, mark it as internal transfer and select the destination journal.
#. Optionally, choose the destination journal payment method.
#. Confirm the payment.

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
