##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.addons.account.report.account_invoice_report import AccountInvoiceReport

def _revert_method(cls, name):
    """ Revert the original method called ``name`` in the given class.
        See :meth:`~._patch_method`.
    """
    method = getattr(cls, name)
    setattr(cls, name, method.origin)


def uninstall_hook(cr, registry):
    _revert_method(AccountInvoiceReport, '_select')
    _revert_method(AccountInvoiceReport, '_from')
