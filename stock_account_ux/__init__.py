from . import models
from . import report
from . import wizard


def post_init_hook(env):
    """Limpia ``account_stock_expense_id`` en las cuentas existentes al instalar."""
    accounts = env["account.account"].sudo().search([("account_stock_expense_id", "!=", False)])
    accounts.write({"account_stock_expense_id": False})
