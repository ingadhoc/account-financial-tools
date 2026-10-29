from odoo import api, fields, models


class ResBank(models.Model):
    # Odoo 20 removed res.bank from base; the catalog is kept here with the same model and fields as 19
    _name = "res.bank"
    _description = "Bank"
    _order = "name, id"
    _rec_names_search = ["name", "bic"]

    name = fields.Char(required=True)
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char()
    city = fields.Char()
    state = fields.Many2one("res.country.state", "Fed. State", domain="[('country_id', '=?', country)]")
    country = fields.Many2one("res.country")
    country_code = fields.Char(related="country.code", string="Country Code")
    email = fields.Char()
    phone = fields.Char()
    active = fields.Boolean(default=True)
    bic = fields.Char("Bank Identifier Code", index=True, help="Sometimes called BIC or Swift.")

    @api.depends("bic")
    def _compute_display_name(self):
        for bank in self:
            bank.display_name = (bank.name or "") + (bank.bic and (" - " + bank.bic) or "")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("bic"):
                vals["bic"] = vals["bic"].upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("bic"):
            vals["bic"] = vals["bic"].upper()
        return super().write(vals)

    @api.onchange("country")
    def _onchange_country_id(self):
        if self.country and self.country != self.state.country_id:
            self.state = False

    @api.onchange("state")
    def _onchange_state(self):
        if self.state.country_id:
            self.country = self.state.country_id
