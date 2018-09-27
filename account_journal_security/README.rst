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

Users can be assigned many Account Journals and then they can be restricted to
see only this Journals.

You can specify for each day that users can write, this module it creates a many2many field between journals and users. If you set users to journal, then this journals and the related moves, will be only seen by selected users. This i usually used for payroll journals.

This fields are only seen by users with 'access right management'::

    *NOTE:* We add auto_joinr to journal_id fields in order to avoid performance issues.

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

#. When posting a journal entry, minimun balance constrains are going to be checked

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/account_financial_tools/issues>`_. In case of trouble, please
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
