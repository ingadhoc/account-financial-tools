from odoo import api
from odoo.addons.account.models.account_move import AccountMove


def monkey_patches():
    # monkey patch
    # Bypasseamos el método _compute_show_reset_to_draft_button de account para que permita volver a borrador
    # si se desmarca en restrict_mode_hash_table en el journal
    # de esta manera se mantiene a formulario para que vaya al super del padre
    def _compute_show_reset_to_draft_button(self):
        for move in self:
            move.show_reset_to_draft_button = (
                not self._is_move_restricted(move)
                and not move.journal_id.restrict_mode_hash_table
                and (move.state == "cancel" or (move.state == "posted" and not move.need_cancel_request))
            )

    AccountMove._compute_show_reset_to_draft_button = _compute_show_reset_to_draft_button

    def _patch_method(cls, name, method):
        origin = getattr(cls, name)
        method.origin = origin
        # propagate decorators from origin to method, and apply api decorator
        wrapped = api.propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    _patch_method(AccountMove, "_compute_show_reset_to_draft_button", _compute_show_reset_to_draft_button)
