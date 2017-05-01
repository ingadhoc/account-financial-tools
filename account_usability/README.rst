.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

==============================
Account Usability Improvements
==============================

Several Improvements to accounting:
#. When creatin banks from bank menu, use bank name + account number for journal name (by default only account number is used). And also allow user to change this value (by default user can't)
#. Make company id not required and false by default on payment term. This field was added on v9 and it is not used anywhere
#. Add debit and credit card payment methods
#. For inbound debit and credit payments, allow to configure days for collection. This will be used to set maturity date of related journal entries
#. Add online payment method on journals
#. Add link between payment acquirer and journals
#. Fix the balance of the "journals" in the accounting table, so that it shows the value of the column "to pay" not "total" as it does until now.
#. Add print invoice button on paid state.
#. Add send email button on bank statement lines to confirm payment to customers.


Installation
============

To install this module, you need to:

#. Just install this module.


Configuration
=============

To configure this module, you need to:

#. No configuration nedeed.


.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.adhoc.com.ar/

.. repo_id is available in https://github.com/OCA/maintainer-tools/blob/master/tools/repos_with_ids.txt
.. branch is "8.0" for example

Known issues / Roadmap
======================

* ...

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/stock/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* ADHOC SA: `Icon <http://fotos.subefotos.com/83fed853c1e15a8023b86b2b22d6145bo.png>`_.

Contributors
------------


Maintainer
----------

.. image:: http://fotos.subefotos.com/83fed853c1e15a8023b86b2b22d6145bo.png
   :alt: Odoo Community Association
   :target: https://www.adhoc.com.ar

This module is maintained by the ADHOC SA.

To contribute to this module, please visit https://www.adhoc.com.ar.
