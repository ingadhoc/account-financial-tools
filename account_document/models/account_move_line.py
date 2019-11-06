from odoo import models, fields


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    # useful to group by this field
    document_type_id = fields.Many2one(
        related='move_id.document_type_id',
        auto_join=True,
        # stored required to group by
        store=True,
        index=True,
    )
