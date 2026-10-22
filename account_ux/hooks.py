from odoo.addons.account.models.account_move import AccountMove
from odoo.addons.account.models.account_payment import AccountPayment


def _revert_method(cls, name):
    """Revertir el método original llamado 'name'"""
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(env):
    _revert_method(AccountPayment, "_compute_available_journal_ids")
    _revert_method(AccountMove, "_compute_show_reset_to_draft_button")
    # Without this, reading journal entries would be left with no company rule at all.
    for xml_id in ("account.account_move_comp_rule", "account.account_move_line_comp_rule"):
        rule = env.ref(xml_id, raise_if_not_found=False)
        if rule:
            rule.perm_read = True
