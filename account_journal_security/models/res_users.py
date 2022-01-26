##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class Users(models.Model):

    _inherit = 'res.users'

    journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_users',
        'user_id',
        'journal_id',
        'Restricted Journals (TOTAL)',
        context={'active_test': False},
    )

    modification_journal_ids = fields.Many2many(
        'account.journal',
        'journal_security_journal_modification_users',
        'user_id',
        'journal_id',
        'Modification Journals',
        context={'active_test': False},
    )

    # Cuando un usuario es archivado limpiamos los campos modification_journal_ids
    # y journal_ids para evitar problemas, ya que en el metodo unset_modification_user_ids(self)
    # no se limpiaban los usuarios archivados.
    # TODO ver mejora para v15 (posible compute/inverse)
    def write(self, vals):
        if 'active' in vals and not vals.get('active'):
            vals.update({
                'modification_journal_ids': [(5, 0, 0)],
                'journal_ids': [(5, 0, 0)],
            })
        return super().write(vals)
