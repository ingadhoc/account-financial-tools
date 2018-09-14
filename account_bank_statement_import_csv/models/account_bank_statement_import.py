# -*- coding: utf-8 -*-
# © 2018 Ivan Todorovich <ivan.todorovich@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import api, fields, models, _
from openerp.tools.safe_eval import safe_eval
from openerp.exceptions import UserError, ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

ENCODINGS = ('utf-8 utf-16 windows-1252 latin1 latin2 big5 ' +
            'gb18030 shift_jis windows-1251 koir8_r').split(' ')

class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    @api.multi
    def import_file(self):
        if self.data_filename and self.data_filename.lower().endswith('.csv'):
            # Read missing information from context, otherwise show wizard
            statement_name = self.env.context.get('statement_name')
            statement_date = self.env.context.get('statement_date')
            csv_template_id = self.env.context.get('csv_template_id')
            if not statement_name or not statement_date or not csv_template_id:
                # The active_id is passed in context so the wizard can call import_file again
		        return {
		            'name': _('Import CSV Bank Statement Wizard'),
		            'type': 'ir.actions.act_window',
		            'res_model': 'account.bank.statement.import.csv',
		            'view_type': 'form',
		            'view_mode': 'form',
		            'target': 'new',
		            'context': {
		                'statement_import_transient_id': self.ids[0],
		            }
		        }

        return super(AccountBankStatementImport, self).import_file()

    @api.model
    def _parse_file(self, data_file):
        if self.data_filename and self.data_filename.lower().endswith('.csv'):
            # Read missing information from context, otherwise show wizard
            statement_name = self.env.context.get('statement_name')
            statement_date = self.env.context.get('statement_date')
            csv_template_id = self.env.context.get('csv_template_id')
            if not statement_name or not statement_date or not csv_template_id:
                # This info should be here by now
                raise UserError(_('Missing statement name or date'))

            # Process file
            template_id = self.env['account.bank.statement.import.csv.template'].browse([csv_template_id])

            # Use base_import.import
            importer = self.env['base_import.import'].create({
            	'file': data_file,
            	'file_name': self.data_filename,
            	'file_type': 'unknown',
            })

            # Options should be saved in template?
            # Or maybe set using the wizard?
            options = {
            	'encoding': template_id.encoding,
            	'separator': template_id.separator,
            	'quoting': template_id.quoting,
                'headers': template_id.headers,
            }

            # Should support all files format supported by base_import (xls / xlsx / ods / csv)
            try:
                data = importer._read_file(importer.file_type, importer, options)
                assert data, _('File seems to have no content.')
            except Exception, e:
                raise UserError(_('Error reading file:\r\n\r\n%s') % str(e))

            # Get header names
            headers = None
            if options.get('headers'):
                headers = next(data)

            # Process transactions
            def _process_row(row):
                return self._csv_process_row(template_id, row, headers)

            transactions = [r for r in [_process_row(row) for row in data] if r]

            res = (None, None, [{
                    'name': statement_name,
                    'date': statement_date,
                    'transactions': transactions,
                }])

            return res

        else:
            return super(AccountBankStatementImport, self)._parse_file(data_file)


    def _csv_process_field(self, field, row, headers=None):

        # Helpers
        def _get_by_name(name):
            if not headers:
                return None
            try:
                return row[headers.index(name)]
            except Exception, e:
                raise UserError(_('Column \'%s\' not found:\r\n%s') % (
                    name, str(row)))

        def _get_by_index(index):
            try:
                return row[index]
            except Exception, e:
                raise UserError(_('Column ID: %g not found:\r\n%s') % (
                    index, str(row)))

        def _col(n):
            if isinstance(n, int):
                return _get_by_index(n)
            else:
                return _get_by_name(n)

        def _safe_float(s):
            if not s:
                return 0.00
            elif isinstance(s, float):
                return s
            elif isinstance(s, int):
                return float(s)
            else:
                if field.replace_comma:
                    s = s.replace('.', '').replace(',', '.')
                    return float(s)

        # Retrieve value
        value = None

        if field.type == 'number':
            value = _get_by_index(field.col_number)
        elif field.type == 'header':
            value = _get_by_name(field.col_header)

        # Execute python transform script
        if field.expr:
            try:
                eval_context = {
                    'value': value,
                    'col': _col,
                    'safe_float': _safe_float,
                    'row': row,
                    'field': field,
                }
                value = safe_eval(str(field.expr), eval_context)
            except Exception, e:
                raise UserError(_(
                    'Evaluation Error for field: %s\r\n\r\n'
                    'Exception:\r\n%s\r\n\r\n'
                    'Python Expression:\r\n%s\r\n\r\n'
                    'Data:\r\n%s'
                    ) % (field.field, str(e), str(field.expr), str(row)))

        # Data transform
        if value and field.field == 'date':
            try:
                value = datetime.strptime(value, field.date_format)
            except Exception, e:
                raise UserError(_('Error reading date: %s (%s)') % (
                    value, field.date_format))

        elif value and field.field == 'amount':
            try:
                value = _safe_float(value)
            except Exception, e:
                raise UserError(_('Error parsing float from \'%s\'') % value)

        return value


    def _csv_process_row(self, template, row, headers=None):
        try:
            res = {}
            for field in template.line_ids:
                field_name = field.custom_field if field.field == 'other' \
                                else field.field
                res[field_name] = self._csv_process_field(field, row, headers)
            # Check if line has 'date'
            if not res.get('date'):
                if template.error_handling == 'ignore_date':
                    _logger.info(
                        'Ignoring line without date: %s' % str(row))
                    return None
                else:
                    raise UserError(
                        _('Line doesn\'t have a date: %s') % str(row))
            return res
        except UserError, e:
            if template.error_handling == 'ignore':
                _logger.info(
                    'Ignoring line with error: %s %s' % (str(e), str(row)))
                return None
            else:
                raise e


class AccountBankStatementImportCSV(models.TransientModel):
    _name = 'account.bank.statement.import.csv'
    _description = 'Import CSV Bank Statement Wizard'

    name = fields.Char('Statement Name', required=True)
    date = fields.Date('Statement Date', required=True)
    template_id = fields.Many2one(
        'account.bank.statement.import.csv.template', 
        'CSV Bank Statement Template',
        required=True,
    )

    @api.multi
    def import_file(self):
        """ Update context and reprocess the statement """
        statement_import_transient = self.env['account.bank.statement.import'].browse(self.env.context['statement_import_transient_id'])
        return statement_import_transient.with_context(
        		statement_name=self.name,
        		statement_date=self.date,
        		csv_template_id=self.template_id.id).import_file()


class AccountBankStatementImportCSVTemplate(models.Model):
    _name = 'account.bank.statement.import.csv.template'
    _description = 'CSV Bank Statement Template'

    name = fields.Char(required=True)

    encoding = fields.Selection(
    	[(e, e) for e in ENCODINGS],
    	required=True,
    	default='utf-8',
    )

    quoting = fields.Char(
    	required=True,
    	default='"',
    )

    separator = fields.Selection([
    	(',', 'Comma'),
    	(';', 'Semicolon'),
    	('\t', 'Tab'),
    	(' ', 'Space')],
    	required=True,
    	default=',',
    )

    headers = fields.Boolean(
    	'Column Headers',
    	help='Use first row as column headers',
    )

    error_handling = fields.Selection([
        ('error', 'Stop Execution'),
        ('ignore_date', 'Ignore lines without date'),
        ('ignore', 'Ignore lines with errors')],
        required=True,
        default='error'
    )

    line_ids = fields.One2many(
    	'account.bank.statement.import.csv.template.line',
    	'template_id',
    )

    @api.constrains('line_ids')
    def _check_line_ids(self):
    	# Check required lines
    	required = ['date', 'name', 'amount']
    	found = [False for i in required]
    	for line in self.line_ids:
    		for i, req in enumerate(required):
    			if line.field == req:
    				found[i] = True
    				break
    	if not all(found):
    		raise ValidationError(_(
    			'These fields are required: %s.') % ', '.join(required))


class AccountBankStatementImportCSVTemplateLine(models.Model):
    _name = 'account.bank.statement.import.csv.template.line'
    _description = 'CSV Bank Statement Template Line'

    _sql_constraints = [
    	('unique_field', 'unique(template_id, field, custom_field)', 
    		_('You can\'t repeat fields in a template'))]

    template_id = fields.Many2one(
    	'account.bank.statement.import.csv.template',
    	'Template')

    type = fields.Selection([
    	('number', 'Number'),
    	('header', 'Header Name'),
    	('expr',   'Computed'),
    	],
    	required=True,
        default='number',
    )

    col_number = fields.Integer('Column Number')
    col_header = fields.Char('Column Name')

    expr = fields.Text('Python Expression')

    field = fields.Selection([
    	('date', 'Date'),
    	('name', 'Name'),
    	('amount', 'Amount'),
    	('partner_name', 'Partner Name'),
        ('account_number', 'Account Number'),
        ('note', 'Note'),
        ('ref', 'Reference'),
        ('unique_import_id', 'Unique Import ID'),
        ('other', 'Other'),
    	],
    	required=True)

    custom_field = fields.Char('Field Name')

    date_format = fields.Char(
        help='The date format that will be used to parse the date.',
        default='%Y-%m-%d',
    )

    replace_comma = fields.Boolean(
        help='Check this if the number is using comma as decimal separator.'
    )

    description = fields.Char(compute='_compute_description')

    @api.multi
    @api.depends('type', 'col_number', 'col_header', 'expr')
    def _compute_description(self):
        for rec in self:
            desc = ''
            if rec.type == 'number':
                desc = _('Column (%g)') % rec.col_number
            elif rec.type == 'header':
                desc = _('Column \'%s\'') % rec.col_header
            elif rec.type == 'expr':
                desc = _('Computed: %s') % rec.expr
            rec.description = desc
