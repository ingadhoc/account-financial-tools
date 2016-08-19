# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
# from openerp import models, fields, api
# import cStringIO
# from openerp import tools
from openerp import pooler, SUPERUSER_ID


def post_init_hook(cr, pool):
    # al final no lo desinstalamos automaticamente porque podria romper otras
    # dependencias o desinstalar modulos que no queremos desinstalar
    # module_pool = pool['ir.module.module']
    # module_ids = module_pool.search(
    #     cr, SUPERUSER_ID,
    #     [('name', '=', 'l10n_multilang'), ('state', '=', 'installed')], {})
    # if not module_ids:
    #     return True
    # print 'install module %s' % module
    # print 'ids for module: %s' % module_ids
    # model.button_install(
    #     cr, SUPERUSER_ID, module_ids, {})
    # print 'module installed'
    return True


def pre_init_hook(cr):
    pool = pooler.get_pool(cr.dbname)
    lang_read = pool['res.lang'].search_read(
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
        ('account.tax.code', 'name'),
        ('account.account.type', 'name'),
        # campos de l10n_multilang
        ('account.account', 'name'),
        ('account.journal', 'name'),
        ('account.analytic.account', 'name'),
        ('account.analytic.journal', 'name'),
        ('account.account.template', 'name'),
        ('account.tax.template', 'name'),
        ('account.tax.code.template', 'name'),
        ('account.chart.template', 'name'),
        ('account.fiscal.position', 'name'),
        ('account.fiscal.position', 'note'),
        ('account.fiscal.position.template', 'name'),
        ('account.fiscal.position.template', 'note'),
    ]
    for model_name, field_name in models_fields:
        sync_field(cr, SUPERUSER_ID, lang_code, model_name, field_name)


def sync_field(cr, uid, lang_code, model_name, field_name):
    pool = pooler.get_pool(cr.dbname)
    translations = pool['ir.translation'].search_read(
        cr, SUPERUSER_ID, [
            ('name', '=', '%s,%s' % (model_name, field_name)),
            ('type', '=', 'model'),
            ('lang', '=', 'es_AR')],
        ['res_id', 'value'])
    for translation in translations:
        table = model_name.replace('.', '_')
        value = translation['value']
        res_id = translation['res_id']
        cr.execute(
            "UPDATE %s SET %s='%s' WHERE id=%s" % (
                table,
                field_name,
                value,
                res_id
            ))
