# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from openupgradelib import openupgrade
from openupgradelib.openupgrade import logged_query

model_renames = [
    # modelos renombrados en l10n_ar_invoice
    # a account_document
    ('afip.document_class', 'account.document.type'),
    ('account.journal.afip_document_class', 'account.journal.document.type'),
    ('afip.document_letter', 'account.document.letter'),
    ('afip.responsability', 'afip.responsability.type'),
    ('account.voucher.receiptbook', 'account.payment.receiptbook'),
]

table_renames = [
    ('afip_document_class', 'account_document_type'),
    ('account_journal_afip_document_class', 'account_journal_document_type'),
    ('afip_document_letter', 'account_document_letter'),
    ('afip_responsability', 'afip_responsability_type'),
    ('account_voucher_receiptbook', 'account_payment_receiptbook'),
    # m2m fields
    ('afip_doc_letter_issuer_rel',
        'account_doc_let_responsability_issuer_rel'),
    ('afip_doc_letter_receptor_rel',
        'account_doc_let_responsability_receptor_rel'),
    ('res_partner_afip_doc_class_rel',
        'res_partner_document_type_rel'),
]

# campos renombrados en l10n_ar_invoice
column_renames = {
    'account_doc_let_responsability_issuer_rel': [
        ('responsability_id', 'afip_responsability_type_id'),
    ],
    'account_doc_let_responsability_receptor_rel': [
        ('responsability_id', 'afip_responsability_type_id'),
    ],
    'res_partner_document_type_rel': [
        ('document_class_id', 'document_type_id'),
    ],
    'account_document_type': [
        ('afip_code', 'code'),
        ('document_type', 'internal_type'),
    ],
    'res_partner': [
        ('responsability_id', 'afip_responsability_type_id'),
    ],
    'account_invoice': [
        ('journal_document_class_id', 'journal_document_type_id'),
        ('afip_document_class_id', 'document_type_id'),
        ('afip_document_number', 'document_number'),
        ('responsability_id', 'afip_responsability_type_id'),
    ],
    'account_move': [
        ('document_class_id', 'document_type_id'),
        # backup old doc number column so we can create new column
        ('document_number', None),
        ('afip_document_number', 'document_number'),
    ],
    'account_journal_document_type': [
        ('afip_document_class_id', 'document_type_id'),
    ],
    'account_payment_receiptbook': [
        # ('type', 'partner_type'),
        ('manual_prefix', 'prefix'),
        ('document_class_id', 'document_type_id'),
    ],
}

# column_copies = {
#     'account_payment_receiptbook': [
#         ('type', None, None),
#     ],
# }


# def delete_invoice_views(cr):
#     """
#     We delete this views that are not deleted automatically and raise an
#     error if we still find some erros we can delete all views by enable
#     remove_views of pre-migration of base 9.0.1.4
#     """
#     openupgrade.logged_query(cr, """
#         DELETE from ir_ui_view iv
#         USING ir_model_data d WHERE iv.id=d.res_id
#         and d.name in (
#             'view_invoice_supplier_payment_doc_number_form',
#             'view_invoice_payment_doc_number_form',
#             'view_move_line_form',
#             'view_account_move_line_filter',
#             'view_move_line_tree',
#             'view_res_partner_form',
#             'view_res_partner_filter',
#             'view_res_partner_tree',
#             'view_partner_form',
#             'view_company_inherit_form',
#             'view_account_journal_ar_form')
#         and d.module in ('account_document','l10n_ar_padron_afip')
#         """,)
#     # view_partner_form is from l10n_ar_padron_afip


def delete_payment_views(cr):
    """
    Vorramos todas las vistas de voucher porque da un error y porque no
    vamos a usar voucher
    """
    cr.execute(
        """\
        DELETE FROM ir_ui_view
        WHERE model = 'account.voucher'
        """
    )


@openupgrade.migrate()
def migrate(cr, version):
    # muchos errores en invoice_views, borramos todo con remove_views en
    # base upgrade 9.0.1.4
    # delete_invoice_views(cr)
    # delete_payment_views(cr)
    openupgrade.rename_models(cr, model_renames)
    openupgrade.rename_tables(cr, table_renames)
    # openupgrade.copy_columns(cr, column_copies)
    openupgrade.rename_columns(cr, column_renames)
    fix_data_on_l10n_ar_account(cr)
    fix_data_of_l10n_ar_account_voucher(cr)
    # TODO si mantenemos lo de borrar todo no haria falta


def fix_data_of_l10n_ar_account_voucher(cr):
    """
    Some modes where from l10n_ar_account_voucher and go to account_document
    Account voucher is deleted so we dont care about that, only receiptbook
    remains
    """
    # on v8 we upload reciptbooks as data, now they come from chart account
    # we delete external ids so they are not deleted
    logged_query(cr, """
        DELETE FROM ir_model_data
        WHERE model in ('account.payment.receiptbook', 'ir.sequence')
        AND module = 'l10n_ar_account_voucher'
        """,)

    old_name = 'l10n_ar_account_voucher'
    new_name = 'account_document'
    # update data, fields and models
    update_models_module_name(
        cr, ['account.voucher.receiptbook'], old_name, new_name)


def fix_data_on_l10n_ar_account(cr):
    """
    because in apriori we rename l10n_ar_invoice to account_document, but
    some things are done on l10n_ar_account, we fix this
    """
    # pasamos de a account_account a l10n_ar_account
    old_name = 'account_document'
    new_name = 'l10n_ar_account'

    # only update data
    l10n_ar_account_data_models = [
        'afip.responsability.type',
        'account.document.type',
        'account.payment.term',
        'account.account.type',
        'account.fiscal.position',
        'res.partner',
    ]
    # update data, fields and models
    l10n_ar_account_models = [
        'afip.responsability.type',
        'afip.incoterm',
        'account.document.letter',
        # 'account.payment.receiptbook',
    ]

    update_data_module_name(
        cr, l10n_ar_account_data_models, old_name, new_name)
    update_models_module_name(
        cr, l10n_ar_account_models, old_name, new_name)

    # this fields are on account_document but they are created by
    # l10n_ar_account
    fields = [
        # 'field_afip_document_class_document_letter_id',
        'field_account_invoice_afip_incoterm_id',
        'field_account_invoice_afip_service_start',
        'field_account_invoice_afip_service_end',
        'field_account_invoice_point_of_sale_type',
        'field_account_invoice_point_of_sale_number',
        'field_account_invoice_afip_responsability_type_id',
        'field_product_uom_afip_code',
        'field_res_country_afip_code',
        'field_res_country_cuit_fisica',
        'field_res_country_cuit_juridica',
        'field_res_country_cuit_otro',
        'field_res_currency_afip_code',
        'field_res_partner_gross_income_number',
        'field_res_partner_gross_income_type',
        'field_res_partner_start_date',
        'field_account_fiscal_position_afip_code',
    ]
    xmlid_renames = [(
        'account_document.%s' % field,
        'l10n_ar_account.%s' % field) for field in fields]
    xmlid_renames += [
        ('account_document.field_afip_document_class_document_letter_id',
            'l10n_ar_account.field_account_document_type_document_letter_id',),
        ('account_document.field_afip_document_letter_issuer_ids',
            'l10n_ar_account.field_account_document_letter_issuer_ids',),
        ('account_document.field_afip_document_letter_receptor_ids',
            'l10n_ar_account.field_account_document_letter_receptor_ids',)
    ]
    openupgrade.rename_xmlids(cr, xmlid_renames)

    # on v8 fiscal position are created by data and also, in some cases, they
    # were created without noupdate=trur, so we deelte external ids
    logged_query(cr, """
        DELETE FROM ir_model_data
        WHERE model = 'account.fiscal.position'
        AND module = 'l10n_ar_account'
        """,)


def update_data_module_name(cr, models, old_name, new_name):
    """
    fix data has been assigend to account_account but is loaded by
    l10n_ar_account
    """
    for model in models:
        query = ("UPDATE ir_model_data SET module = %s "
                 "WHERE module = %s and model = %s")
        logged_query(cr, query, (new_name, old_name, model))


def update_models_module_name(cr, models, old_name, new_name):
    """
    This models are still from l10n_ar_account and not from account_document
    Deal with changed module names of certified modules
    in order to prevent  'certificate not unique' error,
    as well as updating the module reference in the
    XML id.

    :param namespec: tuple of (old name, new name)
    """
    for model in models:
        # renombramos la data
        query = ("UPDATE ir_model_data SET module = %s "
                 "WHERE module = %s and model = %s")
        logged_query(cr, query, (new_name, old_name, model))

        # renombamos la info del model
        query = ("UPDATE ir_model_data SET module = %s "
                 "WHERE module = %s and name = %s and model='ir.model'")
        logged_query(
            cr, query,
            (new_name, old_name, "model_%s" % model.replace('.', '_')))

        # renombamos la info de fields
        query = ("UPDATE ir_model_data SET module = %s "
                 "WHERE module = %s and name LIKE %s "
                 "and model='ir.model.fields'")
        logged_query(
            cr, query,
            (new_name, old_name, "field_%s%%" % model.replace('.', '_')))
