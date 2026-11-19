from odoo.addons.account.models.account_payment import AccountPayment


def _revert_method(cls, name):
    """Revertir el método original llamado 'name'"""
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(env):
    _revert_method(AccountPayment, "_compute_available_journal_ids")
<<<<<<< 8bd27d6f071c7127b5f63935002d366bbf677f4e
||||||| 6ad9cb735c488ece5fbcf91e7455aaec99ec9148
    _revert_method(AccountMove, "_compute_show_reset_to_draft_button")
=======
    _revert_method(AccountMove, "_compute_show_reset_to_draft_button")
    # Without this, reading these records would be left with no company rule at all.
    for xml_id in (
        "account.account_move_comp_rule",
        "account.account_move_line_comp_rule",
        "account.journal_comp_rule",
        "account.account_comp_rule",
        "account.tax_comp_rule",
        "account.tax_group_comp_rule",
        "account.tax_rep_comp_rule",
        "account.account_payment_term_comp_rule",
    ):
        rule = env.ref(xml_id, raise_if_not_found=False)
        if rule:
            rule.perm_read = True
>>>>>>> 2b5e46c061628140efbc26f684346cb2b19f8a3c
