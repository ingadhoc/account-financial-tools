from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Change receipt PDF report name"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = env.ref("account.action_report_payment_receipt")
    report.print_report_name = (
        "(object.partner_type == 'supplier' and 'Orden de Pago' or 'Recibo') + ' ' + (object.name or 'Borrador')"
    )
