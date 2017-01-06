# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    @api.model
    def _prepare_all_journals(
            self, acc_template_ref, company, journals_dict=None):
        """
        Inherit this function in order to create more journals on chart install
        """
        journal_data = super(
            AccountChartTemplate, self)._prepare_all_journals(
            acc_template_ref, company, journals_dict)

        journals = [
            ('Compras (Liquidación de Impuestos)', 'LIMP', 'purchase'),
            ('Compras (Sueldos y Jornales)', 'SYJ', 'purchase'),
            ('Asientos de Apertura / Cierre', 'A/C', 'general'),
        ]

        for name, code, type in journals:
            journal_data.append({
                'type': type,
                'name': name,
                'code': code,
                'company_id': company.id,
                'show_on_dashboard': False,
                'update_posted': True,
            })
        return journal_data
