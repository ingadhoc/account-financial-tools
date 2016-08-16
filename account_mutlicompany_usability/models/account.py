# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import api, models
# from openerp.exceptions import Warning


class AccountAccount(models.Model):

    _inherit = 'account.account'

    @api.multi
    def name_get(self):
        """
        No llamamos a super porque tendriamos que igualmente hacer un read
        para obtener la compania y no queremos disminuir la performance
        """
        res = []
        for record in self:
            record_name = '%s%s%s' % (
                record.code and record.code + ' ' or '',
                record.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    @api.multi
    def name_get(self):
        """
        No llamamos a super porque tendriamos que igualmente hacer un read
        para obtener la compania y no queremos disminuir la performance
        """
        res = []
        for record in self:
            currency = record.currency or record.company_id.currency_id
            record_name = '%s (%s)%s' % (
                record.name,
                currency.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res


class AccountPeriod(models.Model):

    _inherit = 'account.period'

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            record_name = '%s%s' % (
                record.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res


class AccountFiscalyear(models.Model):

    _inherit = 'account.fiscalyear'

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            record_name = '%s%s' % (
                record.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res


class AccountTaxCode(models.Model):
    _inherit = 'account.tax.code'

    @api.multi
    def name_get(self):
        """
        No llamamos a super porque tendriamos que igualmente hacer un read
        para obtener la compania y no queremos disminuir la performance
        """
        res = []
        for record in self:
            record_name = '%s%s%s' % (
                record.code and record.code + ' - ' or '',
                record.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.multi
    def name_get(self):
        """
        No llamamos a super porque tendriamos que igualmente hacer un read
        para obtener la compania y no queremos disminuir la performance
        """
        res = []
        for record in self:
            record_name = '%s%s' % (
                record.description or record.name,
                record.company_id.get_company_sufix())
            res.append((record.id, record_name))
        return res
