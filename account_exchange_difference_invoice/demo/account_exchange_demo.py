import logging

from dateutil.relativedelta import relativedelta
from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _install_exchange_diff_demo(self, companies):
        """Crea data demo para probar este modulo.
        La idea es usar esté método también para instanciar la data de tests.
        Por ahora está utilizando algo de data demo (l10n_ar_tax.res_partner_adhoc_caba, product.product_product_2)
        Eventualemnte, para que los tests NO dependan de data demo, podriamos antes de llamar a este método
        verificar si existen esos registros y crearlos si no existen con esos xmlids para que funcione bien.
        """
        for company in companies.filtered(lambda x: x.country_code == "AR"):
            _logger.info("Creating exchange demo data for company: %s", company.name)
            self = self.with_company(company)

            demo_data = {
                "product.product": self._exchange_diff_invoice_demo_products(),
                "res.currency.rate": self._exchange_diff_invoice_demo_rates(),
                "account.move": self._exchange_diff_invoice_demo_invoices(),
                "account.journal": self._exchange_diff_invoice_demo_journals(),
            }

            # skip_readonly_check es solo para poder hacer pruebas de volver a cargar data
            self.sudo().with_context(skip_pdf_attachment_generation=True, skip_readonly_check=True)._load_data(
                demo_data
            )
            # Set exchange product on the company
            company.exchange_difference_product = self.ref("product_exchange_difference")
            self._exchange_diff_invoice_demo_post_invoices()
            self._exchange_diff_invoice_demo_create_payments()

    @api.model
    def _exchange_diff_invoice_demo_products(self):
        return {
            "product_exchange_difference": {
                "name": "Exchange Rate Difference",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "standard_price": 0.0,
                "list_price": 0.0,
                "default_code": "EXC-DIFF",
                "company_id": False,
            },
        }

    @api.model
    def _exchange_diff_invoice_demo_rates(self):
        first_day_of_month = fields.Date.today() + relativedelta(day=1)
        rates = [1000, 1100, 1200, 1300]  # 01, 02, 03, 04 of actual month
        rates_data = {}
        for days_ago, rate_value in enumerate(rates):
            date_value = first_day_of_month + relativedelta(days=days_ago)
            rates_data[f"exchange_rate_{days_ago}"] = {
                "currency_id": "base.USD",
                "name": date_value.isoformat(),
                "rate": 1 / rate_value,
            }
        return rates_data

    @api.model
    def _exchange_diff_invoice_demo_invoices(self):
        """Create demo invoices in USD with specific amounts and tax breakdown."""
        first_day_of_month = fields.Date.today() + relativedelta(day=1)
        return {
            "demo_invoice_1": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_tax.res_partner_adhoc_caba",
                "currency_id": "base.USD",
                "invoice_date": first_day_of_month,
                "invoice_line_ids": [Command.create({"product_id": "product.product_product_2", "quantity": 1})],
            },
            "demo_invoice_2": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_tax.res_partner_adhoc_caba",
                "currency_id": "base.USD",
                "invoice_date": first_day_of_month + relativedelta(days=1),
                "invoice_line_ids": [Command.create({"product_id": "product.product_product_2", "quantity": 1})],
            },
            "demo_invoice_3": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar_tax.res_partner_adhoc_caba",
                "currency_id": "base.USD",
                "invoice_date": first_day_of_month + relativedelta(days=2),
                "invoice_line_ids": [Command.create({"product_id": "product.product_product_2", "quantity": 1})],
            },
            # otro partner y otra jurisdicción
            "demo_invoice_4": {
                "move_type": "out_invoice",
                "partner_id": "l10n_ar.res_partner_gritti_agrimensura",
                "currency_id": "base.USD",
                "invoice_date": first_day_of_month,
                "invoice_line_ids": [Command.create({"product_id": "product.product_product_2", "quantity": 1})],
            },
        }

    @api.model
    def _exchange_diff_invoice_demo_post_invoices(self):
        invoices = self.env["account.move"]
        for xmlid in self._exchange_diff_invoice_demo_invoices().keys():
            invoices |= self.ref(xmlid)
        invoices.filtered(lambda m: m.state == "draft").action_post()

    @api.model
    def _exchange_diff_invoice_demo_create_payments(self):
        first_day_of_month = fields.Date.today() + relativedelta(day=1)
        for invoices_xml_ids, payment_date in [
            (["demo_invoice_1", "demo_invoice_2"], first_day_of_month + relativedelta(days=2)),
            (["demo_invoice_3"], first_day_of_month + relativedelta(days=3)),
            (["demo_invoice_4"], first_day_of_month + relativedelta(days=1)),
        ]:
            invoices = self.env["account.move"]
            for xmlid in invoices_xml_ids:
                invoices |= self.ref(xmlid)

            amount_residual = sum(invoices.mapped("amount_residual"))
            if not amount_residual:
                continue

            l10n_ar_withholding_vals = []
            # para facturas de clientes las retenciones se agregan manualmente
            # ACTIVAR CUANDO TENGAMOS SOPORTADAS LAS RETENCIONES EN USD
            # if invoices[0].move_type == "out_invoice":
            #     withholding_amount = 1.1
            #     # para jugar con distintos casos usamos la provincia del cliente y suponemos que nos retiene de la misma jurisdicción
            #     tax = self.env["account.tax"].search(
            #         [
            #             ("company_id", "=", invoices[0].company_id.id),
            #             ("l10n_ar_state_id", "!=", invoices[0].partner_id.state_id.id),
            #             ("l10n_ar_state_id.country_id.code", "=", "AR"),
            #             ("l10n_ar_withholding_payment_type", "=", "customer"),
            #         ],
            #         limit=1,
            #     )
            #     l10n_ar_withholding_vals = [
            #         Command.create(
            #             {
            #                 "name": "0001-00000001",
            #                 "tax_id": tax.id,
            #                 "amount": withholding_amount,
            #             }
            #         )
            #     ]
            #     amount_residual -= withholding_amount

            vals = {
                "amount": amount_residual,
                "date": payment_date,
                "journal_id": self.ref("demo_cash_usd").id,
                "l10n_ar_withholding_line_ids": l10n_ar_withholding_vals,
            }
            action_context = invoices.action_register_payment()["context"]
            payment = self.env["account.payment"].with_context(**action_context).create(vals)
            payment.action_post()

    @api.model
    def _exchange_diff_invoice_demo_journals(self):
        return {
            "demo_cash_usd": {
                "name": "Caja USD",
                "type": "cash",
                "currency_id": "base.USD",
            },
        }
