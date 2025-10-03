.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=================
Stock Account UX
=================

Small UI tweak for account moves related to stock valuations.

This module adds a contextual "Reset to Draft" button to account.move forms
(for users in the accounting group) with a clear confirmation message
explaining that inventory valuation entries are not removed by the action
and may be duplicated if re-validated.

Key behaviour
-------------

- Adds a form button (views/account_move_views.xml) that calls the existing
  draft/reset flow but warns about valuation duplication.
- Uses a hidden field (allow_move_with_valuation_cancelation) to control
  visibility.

Installation
------------

#. Just install this module.

Usage
-----

#. Open Accounting > Journal Entries and open a Journal Entry.
#. If applicable, the "Reset to Draft" button appears (account.group_account_invoice).
#. The confirmation explains valuation implications — review before proceeding.

Developer notes
---------------

- Views: views/account_move_views.xml
- Behaviour: models/account_move.py
- Runtime adjustments: monkey_patches.py
- Tests: tests/test_stock_account_ux.py

Bug Tracker
-----------

Report issues at: https://github.com/ingadhoc/account-financial-tools/issues

Credits
-------

Maintained by |company_logo| (|company|).
