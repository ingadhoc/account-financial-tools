.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3


=====
Banks
=====

Odoo 20 no longer provides the Banks model (res.bank). This module keeps it, as in 19.0:

* **Bank catalog**: Banks with name, BIC/SWIFT code, address, phone and email, in Accounting > Configuration > Banks
* **Bank accounts**: Adds the Bank field to bank accounts, bank journals and the bank account setup wizard; choosing a bank fills the bank name and BIC, that can still be edited and follow the changes of the bank

Installation
============

#. Install it from Apps, or as a dependency of a module that needs banks (such as l10n_ar_bank or l10n_latam_check_ux)

Configuration
=============

#. No additional configuration required

Usage
=====

#. **Manage banks**: Go to Accounting > Configuration > Banks to see, search and edit the banks
#. **Configure bank accounts**: When creating a bank account, select its bank; its name and BIC are filled in the account

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
