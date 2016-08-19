Account no Translation
======================

Make accounting fields no translatable.
For this module to work properly, you should also uninstall "l10n_multilang", we suggest you to unintall it after

Models and fields:

* Account Type: Name
* Account Tax Code: Name
* Account Payment Term: Name and Note
* Account Tax: Name

And if you also uninstall l10n_multilang, this fields will also be no translatable:
* Account Journal: Name
* Account Analytic Account: Name
* Account Analytic Journal: Name
* Account Account: Name
