Account no Translation
======================

This module sets the translatable fields of the accounting objects (name,
descriptions) to non-translatable fields.

This change is usefull for companies that work with only one language.

IMPORTANT: this module will uninstall "l10n_multilang" if installed (and any module that depend on it). It will also sync the values of translations of first installed language (different from en_US) as source values.

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
