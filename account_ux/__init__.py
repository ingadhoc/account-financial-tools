##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from . import reports
from . import models
from . import wizards
<<<<<<< HEAD


def _change_receipt_name(env):
    report = env.ref("account.action_report_payment_receipt")
    report.print_report_name = (
        "(object.partner_type == 'supplier' and 'Orden de Pago' or 'Recibo') + ' ' + (object.name or 'Borrador')"
    )
||||||| parent of 119a6a5b (temp)
=======
from .tests.monkey_patches import monkey_patches
>>>>>>> 119a6a5b (temp)
