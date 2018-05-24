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

It adds new ways to see partner debt:

* Two new tabs (customer debt / supplier debt) on partner form showing the detail of all unreconciled lines with amount on currencies, financial amount and cumulative amounts
* New button from partner to display all the history for a partner
* Add partner balance
* You can send email to one or multiple partners with they debt report

By default all lines of same document are grouped and minimun maturity date of the move line is shown, you can change this behaviur by:
#. Create / modify parameter "account_debt_management.date_maturity_type" with one of the following values:

    #. detail: lines will be splitted by maturity date
    #. max: one line per document, max maturity date shown
    #. min (default value if no parameter or no matching): one line per document, min maturity date shown.

IMPORTANT: this modules isn't compatible with account_journal_security or account_multi_store module. This mudule allows user to see all debt lines no matter journals restrictions

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
