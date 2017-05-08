# -*- coding: utf-8 -*-
from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    sync_translations(env)


def sync_translations(env):
    lang_read = env['res.lang'].search_read(
        ['&', ('active', '=', True), ('translatable', '=', True),
            ('code', '!=', 'en_US')], ['code'], limit=1)
    if not lang_read:
        # no need to sync translations, only en_us language
        return True
    lang_code = lang_read[0]['code']
    models_fields = [
        ('account.tax', 'description'),
    ]
    for model_name, field_name in models_fields:
        sync_field(env, lang_code, model_name, field_name)


def sync_field(env, lang_code, model_name, field_name):
    _logger.info('Syncking translations for model %s, field %s' % (
        model_name, field_name))
    # pool = RegistryManager.get(cr.dbname)
    translations = env['ir.translation'].search_read(
        [
            ('name', '=', '%s,%s' % (model_name, field_name)),
            ('type', '=', 'model'),
            ('lang', '=', 'es_AR')],
        ['res_id', 'value'])
    for translation in translations:
        table = model_name.replace('.', '_')
        value = translation['value']
        res_id = translation['res_id']
        # just in case some constraint block de renaiming
        # try:
        # no nos anduvo, arrojamos el error y listo
        env.cr.execute(
            "UPDATE %s SET %s='%s' WHERE id=%s" % (
                table,
                field_name,
                value,
                res_id
            ))
