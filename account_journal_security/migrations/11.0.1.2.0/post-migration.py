from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env.cr, 'account_journal_security',
        'migrations/11.0.1.2.0/mig_data.xml')
