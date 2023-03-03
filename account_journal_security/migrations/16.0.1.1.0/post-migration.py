from openupgradelib import openupgrade

# Acá aplico los cambios de la vista que modifiqué
@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env.cr, 'account_journal_security',
        'migrations/16.0.1.1.0/mig_data.xml')
