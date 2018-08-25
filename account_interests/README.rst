.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

====================
Interests Management
====================

This module lets us to defined a set of interests rules in our company to then
automatically create interests invoices via a scheduled action run every day.

.. image:: /account_interests/static/src/img/image1.png
   :width: 70%

One invoice will be created for each partner which has been dues that match
with the interest rules.

**TODO:**

* Ver si queremos que tambien se calcule interes proporcional para lo que
  vencio en este ultimo periodo
* Ver si agregamos una fecha en partner ultima fecha de intereses y que
  completemos cuando creamos la factura asi podemos hacer un commit luego de
  cada una y si se rompe podemos recuperar.

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. In order to used please configure the interest in the company form

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
