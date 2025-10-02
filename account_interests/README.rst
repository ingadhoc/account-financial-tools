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

Interest Configuration Fields
=============================

This module provides the following configuration fields for calculating interests:

**Rule Type (Recurrency):** Defines the frequency of interest calculation (daily, weekly, monthly, yearly).

**Repeat Every (Interval):** Specifies how often the interest calculation runs.

**Date of Next Invoice:** Date when the next interest invoice will be generated.

**Automatic Validation:** If enabled, interest invoices will be automatically validated.

**First Due Interest Rate:** Interest rate applied when debt becomes overdue for the first time. Values should be specified as decimals (e.g., 0.10 equals 10%). This corresponds only to the period between issue date and first due date. The interest rate depends on recurrence - if monthly, the rate is monthly and prorated daily based on how many days the invoice was overdue.

**Subsequent Due Interest Rate:** Interest rate applied to balances already overdue for at least one period. Values should be specified as decimals (e.g., 0.10 equals 10%). Calculated for complete periods (e.g., 30 days if monthly), as the debt is considered unpaid for the entire time since the first due date.

**Apply Late Payment Interest:** If enabled, interest will be charged when payment is made after the due date, even if the debt is already settled. The type of interest applied depends on the time elapsed since due date. If payment occurs between first due date and subsequent due date, the applicable interest will be "First Due Interest Rate" for the number of days between payment and first due date, and will be added in the next interest run. If payment occurs after the second due date, the applicable interest will be "Subsequent Due Interest Rate" for the number of days between payment and previous due date, and will be added in subsequent interest runs.

Usage
=====

Step-by-step usage guide:

**1. Configure Interest Rules:**
   - Go to Accounting > Configuration > Companies
   - Select your company
   - Navigate to the "Interest" tab
   - Configure the following settings:

     * **Rule Type:** Choose frequency (daily, weekly, monthly, yearly)
     * **Repeat Every:** Set interval (e.g., 1 for every month)
     * **First Due Interest Rate:** Set rate for first-time overdue (e.g., 0.02 for 2%)
     * **Subsequent Due Interest Rate:** Set rate for already overdue amounts
     * **Apply Late Payment Interest:** Enable if you want to charge interest on late payments
     * **Automatic Validation:** Enable for automatic invoice validation

**2. Set Up the Scheduled Action:**
   - The module includes a scheduled action that runs daily
   - Go to Settings > Technical > Automation > Scheduled Actions
   - Find "Recurring Interest Invoices"
   - Ensure it's active and properly configured

**3. How Interest Calculation Works:**
   - The system automatically identifies overdue invoices based on due dates
   - Calculates interest according to your configured rates
   - Creates interest invoices for each partner with qualifying overdue amounts

**4. Monitor Interest Invoices:**
   - Generated interest invoices appear in Accounting > Customers > Customer Invoices
   - Filter by product to see only interest invoices
   - Review and validate manually if automatic validation is disabled

**5. Handle Exceptions:**
   - Companies with calculation errors are temporarily bypassed
   - Check company messages for error notifications
   - Fix configuration issues and the system will retry in the next run

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
