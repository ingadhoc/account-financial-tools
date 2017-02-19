.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=======================
Account Debt Management
=======================

It adds new ways to see partner debt:

* Two new tabs (customer debt / supplier debt) on partner form showing the
detail of all unreconciled lines with amount on currencies, financial amount
and cumulative amounts
* New button from partner to display all the history for a partner
* Add partner balance
* You can send email to one or multiple partners with they debt report

By default all lines of same document are grouped and minimun maturity date of the move line is shown, you can change this behaviur by:
#. Create / modify parameter "account_debt_management.date_maturity_type" with one of the following values:
    #. detail: lines will be splitted by maturity date
    #. max: one line per document, max maturity date shown
    #. min (default value if no parameter or no matching): one line per document, min maturity date shown.


Installation
============

To install this module, you need to:

#. Just install this module

Configuration
=============

To configure this module, you need to:

#. Go to partners
#. From one partner o sellecting multiple ones, choose "Print / Account Debt Report"

Usage
=====

To use this module, you need to:

#. Go to ...

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
<https://github.com/ingadhoc/{project_repo}/issues>`_. In case of trouble, please
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
