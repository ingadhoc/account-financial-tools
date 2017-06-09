# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
# from openerp import models, fields, api
# import cStringIO
# from openerp import tools
from openerp import SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Desinstalamos l10n_multilang si está instalado, no debería ser muy
    peligroso porque solo modulos de plan de cuentas dependeria de el
    """
    sync_translations(cr, registry)

    module_pool = registry['ir.module.module']
    module_ids = module_pool.search(
        cr, SUPERUSER_ID,
        [('name', '=', 'l10n_multilang'), ('state', '=', 'installed')], {})
    if not module_ids:
        return True
    _logger.info('Uninstalling module "l10n_multilang"')
    module_pool.button_uninstall(
        cr, SUPERUSER_ID, module_ids, {})
    _logger.info('Module "l10n_multilang" sucessfully uninstalled')
    return True


def sync_translations(cr, registry):
    lang_read = registry['res.lang'].search_read(
        cr, SUPERUSER_ID, [
            '&', ('active', '=', True), ('translatable', '=', True),
            ('code', '!=', 'en_US')], ['code'], limit=1)
    if not lang_read:
        # no need to sync translations, only en_us language
        return True
    lang_code = lang_read[0]['code']
    models_fields = [
        ('account.payment.term', 'name'),
        ('account.payment.term', 'note'),
        ('account.tax', 'name'),
        ('account.tax', 'description'),
        ('account.tax.group', 'name'),
    ]
    for model_name, field_name in models_fields:
        sync_field(
            cr, registry, SUPERUSER_ID, lang_code, model_name, field_name)


def sync_field(cr, registry, uid, lang_code, model_name, field_name):
    _logger.info('Syncking translations for model %s, field %s' % (
        model_name, field_name))
    # pool = RegistryManager.get(cr.dbname)
    translations = registry['ir.translation'].search_read(
        cr, SUPERUSER_ID, [
            ('name', '=', '%s,%s' % (model_name, field_name)),
            ('type', '=', 'model'),
            ('lang', '=', 'es_AR')],
        ['res_id', 'value'])
    for translation in translations:
        table = model_name.replace('.', '_')
        value = translation['value']
        # algunas veces la trad es vacias
        if not value:
            continue
        res_id = translation['res_id']
        _logger.info('Syncking on res_id %s, value %s, field_name %s' % (
            res_id, value, field_name))
        # just in case some constraint block de renaiming
        # try:
        # no nos anduvo, arrojamos el error y listo
        cr.execute(
            "UPDATE %s SET %s='%s' WHERE id=%s" % (
                table,
                field_name,
                value,
                res_id
            ))
        # except Exception, e:
        #     _logger.warning(
        #         'Could not update translation on table %s for res_id %s, '
        #         'field %s, with value %s. This is what we get %s' % (
        #             table, res_id, field_name, value, e))
