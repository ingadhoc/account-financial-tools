from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    acc_pay_methods_xml_ids = ['account_ux.account_payment_method_inbound_debit_card',
                     'account_ux.account_payment_method_outbound_debit_card',
                     'account_ux.account_payment_method_inbound_credit_card',
                     'account_ux.account_payment_method_outbound_credit_card',
                     'account_ux.account_payment_method_outbound_online',
                     'account_ux.account_payment_method_inbound_online']
    journals = env['account.journal'].search([])
    for xml_id in acc_pay_methods_xml_ids:
        acc_pay_methods = env.ref(xml_id)
        if journals.filtered(lambda j: acc_pay_methods not in j.available_payment_method_ids):
            acc_pay_methods.unlink()
