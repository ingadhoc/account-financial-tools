from odoo import models, fields, api
# from odoo.exceptions import UserError


class WizardMultiChartsAccounts(models.TransientModel):
    _inherit = 'wizard.multi.charts.accounts'

    @api.multi
    def execute(self):
        """
        When we load a chart of account and set a default tax, add this tax
        to every product
        """
        res = super(WizardMultiChartsAccounts, self).execute()

        # get for detault tax and supplier tax setted for this company

        tax_ids = self.env['ir.values'].get_default(
            'product.template', 'taxes_id', for_all_users=True,
            company_id=self.company_id.id, condition=False)
        supplier_taxes_ids = self.env['ir.values'].get_default(
            'product.template', 'supplier_taxes_id', for_all_users=True,
            company_id=self.company_id.id, condition=False)

        prod_templates = self.env['product.template'].search([])
        if self.sale_tax_id and tax_ids:
            prod_templates.write({
                'taxes_id': [(4, tax_ids[0], None)],
            })
        if self.purchase_tax_id and supplier_taxes_ids:
            prod_templates.write({
                'supplier_taxes_id': [(4, supplier_taxes_ids[0], None)],
            })
        return res


class AccountConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    sale_use_documents = fields.Boolean(
        'Sale Use Documents'
    )
    purchase_use_documents = fields.Boolean(
        'Purchase Use Documents'
    )
    localization = fields.Selection(
        related='company_id.localization',
        # readonly=True,
    )

    @api.onchange('chart_template_id')
    def account_documentonchange_chart_template(self):
        # if user already set localization on company we dont want to overwrite
        # it
        if not self.localization and self.chart_template_id.localization:
            self.localization = self.chart_template_id.localization

    @api.onchange('localization')
    def account_documentonchange_localization(self):
        if self.localization:
            self.sale_use_documents = True
            self.purchase_use_documents = True

    @api.multi
    def set_chart_of_accounts(self):
        """
        We send this value in context because to use them on journals creation
        """
        return super(AccountConfigSettings, self.with_context(
            sale_use_documents=self.sale_use_documents,
            purchase_use_documents=self.purchase_use_documents,
        )).set_chart_of_accounts()
