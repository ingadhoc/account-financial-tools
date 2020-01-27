from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    """
    The objective of this is delete the original view form the module how bring the functionality
    adding in the previous commit
    """
    view = env.ref('account_multicompany_ux.res_config_settings_view_form', raise_if_not_found=False)
    if view:
        view.unlink()
