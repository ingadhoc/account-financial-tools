from odoo import api
from odoo.addons.account.report.account_invoice_report import AccountInvoiceReport

def monkey_patches():

    # monkey patch
    @api.model
    def _select_patch(self):
        return '''
        WITH currency_rate AS MATERIALIZED (
                        SELECT
                        r.currency_id,
                        COALESCE(r.company_id, c.id) as company_id,
                        1/r.rate as rate,
                        r.name AS date_start,
                        (SELECT name FROM res_currency_rate r2
                        WHERE r2.name > r.name AND
                                r2.currency_id = r.currency_id AND
                                (r2.company_id = c.id)
                        ORDER BY r2.name ASC
                        LIMIT 1) AS date_end
                    FROM res_currency_rate r
                    JOIN res_company c ON (r.company_id = c.id)
                    WHERE c.id = %s
            )
            SELECT
                line.id,
                line.move_id,
                line.product_id,
                line.account_id,
                line.journal_id,
                line.company_id,
                line.company_currency_id,
                line.partner_id AS commercial_partner_id,
                account.account_type AS user_type,
                move.state,
                move.move_type,
                move.partner_id,
                move.invoice_user_id,
                move.fiscal_position_id,
                move.payment_state,
                move.invoice_date,
                move.invoice_date_due,
                uom_template.id                                             AS product_uom_id,
                template.categ_id                                           AS product_categ_id,
                line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS quantity,
                CASE
                WHEN rc_currency_id <> line.company_currency_id THEN -line.balance * line.rate
                WHEN rc_currency_id is null THEN line.price_total
                ELSE -line.balance  END AS price_subtotal,
                line.price_total * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS price_total,
                CASE
                WHEN rc_currency_id <> line.company_currency_id THEN
                 -COALESCE(
                   -- Average line price
                   (line.balance / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0) * line.rate
                WHEN rc_currency_id is null THEN COALESCE(
                   -- Average line price
                   (line.price_total / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0)
                ELSE -COALESCE(
                   -- Average line price
                   (line.balance / NULLIF(line.quantity, 0.0)) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0) END
                AS price_average,
                COALESCE(partner.country_id, commercial_partner.country_id) AS country_id,
                line.currency_id                                            AS currency_id
        ''' % self.env.company.id

    @api.model
    def _from_patch(self):
        return '''
            FROM (
                SELECT aml.*, currency_table.rate, rc.currency_id as rc_currency_id
                FROM account_move_line aml
                lEFT JOIN currency_rate currency_table on (
                    (currency_table.currency_id = aml.currency_id) and
                    currency_table.date_start <= COALESCE(aml.date, NOW()) and
                    (currency_table.date_end IS NULL OR currency_table.date_end > COALESCE(aml.date, NOW())))
                LEFT JOIN res_company rc on rc.id=currency_table.company_id
                )AS line
                LEFT JOIN res_partner partner ON partner.id = line.partner_id
                LEFT JOIN product_product product ON product.id = line.product_id
                LEFT JOIN account_account account ON account.id = line.account_id
                LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                LEFT JOIN uom_uom uom_line ON uom_line.id = line.product_uom_id
                LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                INNER JOIN account_move move ON move.id = line.move_id
                LEFT JOIN res_partner commercial_partner ON commercial_partner.id = move.commercial_partner_id
        '''

    def _patch_method(cls, name, method):
        origin = getattr(cls, name)
        method.origin = origin
        # propagate decorators from origin to method, and apply api decorator
        wrapped = api.propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    _patch_method(AccountInvoiceReport, '_select', _select_patch)
    _patch_method(AccountInvoiceReport, '_from', _from_patch)
