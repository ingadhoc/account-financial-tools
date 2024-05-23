from openupgradelib import openupgrade
import logging
logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):

    if env['ir.module.module'].search([('name', '=', 'l10n_ar_edi_ux'),('state', '=', 'installed')]):
        logger.info('Forzamos la eliminamos las vistas que contienen el check_debit_journal_id')
        env.cr.execute("DELETE FROM ir_ui_view WHERE arch_db::text LIKE '%check_debit_journal_id%'")

    logger.info('Forzamos la actualización de la vista de account_journal_views en módulo account.payment para que pueda aplicarse correctamente este cambio https://github.com/odoo/odoo/pull/164208/')
    openupgrade.load_data(env, 'account_payment', 'views/account_journal_views.xml')
