from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    price_dp = env['decimal.precision'].search(
        [('name', '=', 'Product Price')])
    report_price_dp = env['decimal.precision'].search(
        [('name', '=', 'Report Product Price')])
    if price_dp and report_price_dp:
        report_price_dp.digits = price_dp.digits
