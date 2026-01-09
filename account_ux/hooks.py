from odoo.addons.account.models.account_move import AccountMove
from odoo.addons.account.models.account_payment import AccountPayment


def _revert_method(cls, name):
    """Revertir el método original llamado 'name'"""
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(env):
    _revert_method(AccountPayment, "_compute_available_journal_ids")
    _revert_method(AccountMove, "_compute_show_reset_to_draft_button")
