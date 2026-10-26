.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

================
Journal Security
================

Restrict the use of certain journals to certain users. Each journal can have one of these restrictions:

* **Total**: only the selected users can see the journal and its journal entries, journal items and payments.
* **Modification**: every user can see the journal data, but only the selected users can create, modify or delete journal entries and payments of the journal. Other users can still write journal items, so that reconciliations keep working.

The restrictions are access domains (``security/ir.access.csv``) without group, so they apply to every user except the superuser. A user cannot restrict a journal without including themselves.

This fields are only seen by users with 'access right management'::

    *NOTE:* We set bypass_search_access on account.move journal_id field in order to avoid performance issues.

Installation
============

To install this module, you need to:

#. Just install this module

Configuration
=============

To configure this module, you need to:

#. Go to Accounting / Configuration / Journals and set the journals restrictions. use radio button to select what kind of restriction applies to the journal and set the related users.

Usage
=====

To use this module, you need to:

#. Users without access to a restricted journal do not get it as an option when registering a payment or a batch payment.
#. Users without access to a totally restricted journal do not see its entries, journal items or payments.

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
