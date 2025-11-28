from odoo.addons.account.models.account_move import AccountMove


def _revert_method(cls, name):
    """Revert the original method called ``name`` in the given class.
    See :meth:`~._patch_method`.
    """
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(env):
    _revert_method(AccountMove, "_compute_show_reset_to_draft_button")
