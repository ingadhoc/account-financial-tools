import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _install_exchange_diff_demo(self, companies):
        # Just ARG companies for now
        if not companies:
            _logger.info("No companies provided for exchange demo data creation, skipping.")
            return

        _logger.info("Creating exchange demo data for companies: %s", companies.mapped("name"))

        for company in companies.filtered(lambda x: x.country_code == "AR"):
            self = self.with_company(company)

            # Skip if demo data already exists to avoid duplicates on reinstall
            # Check for a specific XML ID created by this module's demo data
            demo_marker = self.env.ref(
                "account_exchange_difference_invoice.demo_exchange_diff_installed_%s" % company.id,
                raise_if_not_found=False,
            )
            if demo_marker:
                _logger.info("Demo data already exists for company %s, skipping creation", company.name)
                continue

            self._create_exchange_rate_demo_data()
            invoices = self._create_exchange_difference_demo_invoices()
            self._create_exchange_difference_demo_payment(invoices)

            # Create marker to indicate demo data has been installed for this company
            self.env["ir.model.data"].create(
                {
                    "name": "demo_exchange_diff_installed_%s" % company.id,
                    "module": "account_exchange_difference_invoice",
                    "model": "res.company",
                    "res_id": company.id,
                }
            )

    def _create_exchange_rate_demo_data(self):
        """Create some USD exchange rates for demo purposes for today and the past 3 months."""
        currency_usd = self.env.ref("base.USD")
        company = self.env.company
        exchange_rate_model = self.env["res.currency.rate"]
        today = date.today()
        rates = [1300, 1200, 1100, 1000]  # today, 1 month ago, 2 months ago, 3 months ago
        for months_ago, rate_value in enumerate(rates):
            date_value = today + relativedelta(months=-months_ago)

            # Check if rate already exists for this date
            existing_rate = exchange_rate_model.search(
                [
                    ("name", "=", date_value.isoformat()),
                    ("currency_id", "=", currency_usd.id),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )

            if not existing_rate:
                exchange_rate_model.create(
                    {
                        "name": date_value.isoformat(),
                        "rate": 1 / rate_value,
                        "currency_id": currency_usd.id,
                        "company_id": company.id,
                    }
                )
                _logger.info("Created exchange rate for %s: %s", date_value, rate_value)
            else:
                _logger.info("Exchange rate already exists for %s, skipping", date_value)

    def _get_demo_partner(self):
        """Return a partner for demo invoices."""
        partner = self.env.ref("base.res_partner_12", raise_if_not_found=False)
        if partner:
            return partner
        return self.env["res.partner"].search([("company_id", "=", self.env.company.id)], limit=1) or self.env[
            "res.partner"
        ].search([], limit=1)

    def _get_caba_fiscal_position(self):
        """Return fiscal position for 'Percepciones CABA' if it exists."""
        return self.env["account.fiscal.position"].search(
            [("name", "ilike", "Percepciones CABA"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

    def _create_exchange_difference_demo_invoices(self):
        """Create demo invoices in USD with specific amounts and tax breakdown."""
        currency_usd = self.env.ref("base.USD", raise_if_not_found=False)

        # Get partner
        partner = self.env.ref("base.res_partner_12", raise_if_not_found=False)
        if not partner:
            partner = self.env["res.partner"].search([("company_id", "=", self.env.company.id)], limit=1)

        # Get different partner for invoice3
        partner2 = self.env.ref("base.res_partner_3", raise_if_not_found=False)
        if not partner2:
            partner2 = self.env["res.partner"].search([("company_id", "=", self.env.company.id)], limit=1, offset=1)
            if not partner2:
                partner2 = partner

        # Get fiscal position
        fiscal_position = self.env["account.fiscal.position"].search(
            [("name", "ilike", "Percepciones CABA"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

        # Get document type for Argentina (Factura A)
        document_type = self.env["l10n_latam.document.type"].search(
            [("code", "=", "1"), ("country_id.code", "=", "AR")],
            limit=1,
        )

        # Get taxes
        vat_21 = self.env["account.tax"].search(
            [("company_id", "=", self.env.company.id), ("type_tax_use", "=", "sale"), ("amount", "=", 21)],
            limit=1,
        )
        vat_10_5 = self.env["account.tax"].search(
            [("company_id", "=", self.env.company.id), ("type_tax_use", "=", "sale"), ("amount", "=", 10.5)],
            limit=1,
        )
        percep_3 = self.env["account.tax"].search(
            [("company_id", "=", self.env.company.id), ("type_tax_use", "=", "sale"), ("amount", "=", 3)],
            limit=1,
        )

        # Invoice 1: Neto 21% (100) + IVA 21% (21) + Neto 10.5% (100) + IVA 10.5% (10.5) + Percep 3% (6) = 237.5 USD @ TC 1000
        invoice1 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "currency_id": currency_usd.id if currency_usd else self.env.company.currency_id.id,
                "invoice_date": date.today(),
                "fiscal_position_id": fiscal_position.id if fiscal_position else False,
                "l10n_latam_document_type_id": document_type.id if document_type else False,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Product with VAT 21% + Percep 3%",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, (vat_21 + percep_3).ids if vat_21 and percep_3 else vat_21.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Product with VAT 10.5% + Percep 3%",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, (vat_10_5 + percep_3).ids if vat_10_5 and percep_3 else vat_10_5.ids)],
                        },
                    ),
                ],
            }
        )
        # Set exchange rate to 1000 before posting
        if currency_usd:
            invoice1.write({"currency_id": currency_usd.id})
        invoice1.action_post()

        # Invoice 2: Neto 21% (150) + IVA 21% (31.5) + Neto 10.5% (500) + IVA 10.5% (52.5) + Percep 3% (19.5) = 753.5 USD @ TC 1100
        invoice2 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "currency_id": currency_usd.id if currency_usd else self.env.company.currency_id.id,
                "invoice_date": date.today(),
                "fiscal_position_id": fiscal_position.id if fiscal_position else False,
                "l10n_latam_document_type_id": document_type.id if document_type else False,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Product with VAT 21% + Percep 3%",
                            "quantity": 1,
                            "price_unit": 150.0,
                            "tax_ids": [(6, 0, (vat_21 + percep_3).ids if vat_21 and percep_3 else vat_21.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Product with VAT 10.5% + Percep 3%",
                            "quantity": 1,
                            "price_unit": 500.0,
                            "tax_ids": [(6, 0, (vat_10_5 + percep_3).ids if vat_10_5 and percep_3 else vat_10_5.ids)],
                        },
                    ),
                ],
            }
        )
        if currency_usd:
            invoice2.write({"currency_id": currency_usd.id})
        invoice2.action_post()

        # Invoice 3: Neto 21% (100) + IVA 21% (21) = 121 USD @ TC 1000
        invoice3 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner2.id,
                "currency_id": currency_usd.id if currency_usd else self.env.company.currency_id.id,
                "invoice_date": date.today(),
                "fiscal_position_id": fiscal_position.id if fiscal_position else False,
                "l10n_latam_document_type_id": document_type.id if document_type else False,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Product with VAT 21%",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, vat_21.ids if vat_21 else [])],
                        },
                    ),
                ],
            }
        )
        if currency_usd:
            invoice3.write({"currency_id": currency_usd.id})
        invoice3.action_post()

        _logger.info(
            "Created demo invoices: %s (237.5 USD @ TC 1000), %s (753.5 USD @ TC 1100), %s (121 USD @ TC 1000)",
            invoice1.name,
            invoice2.name,
            invoice3.name,
        )

        return invoice1 + invoice2 + invoice3

    def _create_exchange_difference_demo_payment(self, invoices):
        """Create a payment that pays the demo invoices."""
        if not invoices:
            return

        # Get bank journal
        bank_journal = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        # Calculate amounts: 991 USD at rate 1200 = 1,189,200 ARS
        usd_currency = self.env.ref("base.USD")
        counterpart_amount_usd = 991.0
        exchange_rate = 1200.0
        amount_ars = counterpart_amount_usd * exchange_rate

        # Create payment
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoices[0].partner_id.id,
                "amount": amount_ars,
                "currency_id": self.env.company.currency_id.id,
                "date": date.today(),
                "journal_id": bank_journal.id,
                "counterpart_exchange_rate": exchange_rate,
                "counterpart_currency_id": usd_currency.id,
                "counterpart_currency_amount": counterpart_amount_usd,
            }
        )

        payment.action_post()

        _logger.info("Created demo payment: %s", payment.name)

        # Create payment for invoice3: 121 USD at rate 1100
        if len(invoices) > 2:
            invoice3 = invoices[2]
            counterpart_amount_usd_inv3 = 121.0
            exchange_rate_inv3 = 1100.0
            amount_ars_inv3 = counterpart_amount_usd_inv3 * exchange_rate_inv3

            payment3 = self.env["account.payment"].create(
                {
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": invoice3.partner_id.id,
                    "amount": amount_ars_inv3,
                    "currency_id": self.env.company.currency_id.id,
                    "date": date.today(),
                    "journal_id": bank_journal.id,
                    "counterpart_exchange_rate": exchange_rate_inv3,
                    "counterpart_currency_id": usd_currency.id,
                    "counterpart_currency_amount": counterpart_amount_usd_inv3,
                }
            )

            payment3.action_post()

            _logger.info("Created demo payment for invoice3: %s", payment3.name)
