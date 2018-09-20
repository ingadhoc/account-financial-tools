from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    module = env['ir.module.module'].search(
        [('name', '=', 'account_move_helper')])
    module.with_context(overwrite=True)._update_translations()
