# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
# from openerp import models, fields, api
# import cStringIO
# from openerp import tools
from openerp import SUPERUSER_ID
# from openerp.modules.registry import RegistryManager
import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, pool):
    """
    Desinstalamos l10n_multilang si está instalado, no debería ser muy
    peligroso porque solo modulos de plan de cuentas dependeria de el
    """
    module_pool = pool['ir.module.module']
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


def pre_init_hook(cr):
    # pool = RegistryManager.get(cr.dbname)
    # lang_read = pool['res.lang'].search_read(
    #     cr, SUPERUSER_ID, [
    #         '&', ('active', '=', True), ('translatable', '=', True),
    #         ('code', '!=', 'en_US')], ['code'], limit=1)
    query = ("""
        SELECT code FROM res_lang
        WHERE
            active = true and translatable = true and code != 'en_US'
        """)
    cr.execute(query)
    lang_read = cr.fetchall()
    if not lang_read:
        # no need to sync translations, only en_us language
        return True
    lang_code = lang_read[0][0]
    models_fields = [
        ('account.payment.term', 'name'),
        ('account.payment.term', 'note'),
        ('account.tax', 'name'),
        ('account.tax.group', 'name'),
        # a este al final lo dejamos
        # ('account.account.type', 'name'),
        # campos de l10n_multilang
        ('account.account', 'name'),
        ('account.journal', 'name'),
        ('account.analytic.account', 'name'),
        # ('account.analytic.journal', 'name'),
        ('account.account.template', 'name'),
        ('account.tax.template', 'name'),
        ('account.chart.template', 'name'),
        ('account.fiscal.position', 'name'),
        ('account.fiscal.position', 'note'),
        ('account.fiscal.position.template', 'name'),
        ('account.fiscal.position.template', 'note'),
    ]
    for model_name, field_name in models_fields:
        sync_field(cr, SUPERUSER_ID, lang_code, model_name, field_name)


def sync_field(cr, uid, lang_code, model_name, field_name):
    _logger.info('Syncking translations for model %s, field %s' % (
        model_name, field_name))
    # pool = RegistryManager.get(cr.dbname)
    # translations = pool['ir.translation'].search_read(
    #     cr, SUPERUSER_ID, [
    #         ('name', '=', '%s,%s' % (model_name, field_name)),
    #         ('type', '=', 'model'),
    #         ('lang', '=', 'es_AR')],
    #     ['res_id', 'value'])
    # dont know why but old method of searc_red is not working
    query = ("""
        SELECT res_id, value FROM ir_translation
        WHERE
            name = '%s' and type = 'model' and lang = 'es_AR'
        """ % (
        "%s,%s" % ('product.template', 'description_sale')))
    cr.execute(query)
    translations = cr.fetchall()
    for translation in translations:
        table = model_name.replace('.', '_')
        res_id, value = translation
        # value = translation['value']
        # res_id = translation['res_id']
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
