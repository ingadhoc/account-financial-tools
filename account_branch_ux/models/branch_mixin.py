from odoo import api, fields, models


class BranchMixin(models.AbstractModel):
    _name = 'branch.mixin'
    _description = 'Branch Mixin'

    branch_company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    main_company_id = fields.Many2one(
        "res.company",
        compute="_compute_main_company",
    )

    @api.depends("branch_company_id")
    def _compute_main_company(self):
        for rec in self:
            rec.main_company_id = rec.branch_company_id.parent_id or rec.branch_company_id
