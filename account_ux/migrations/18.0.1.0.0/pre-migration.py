from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """
    The objective of this is delete the original view form the module how bring the functionality
    adding in the previous commit
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref('account_ux.view_account_form', raise_if_not_found=False)
    if view:
        view.unlink()
