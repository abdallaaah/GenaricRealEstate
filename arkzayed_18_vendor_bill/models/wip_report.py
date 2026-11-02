# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class WipReport(models.Model):
    _name = "wip.report"
    _description = "WIP Report"
    _auto = False
    _order = "vendor_id, scope_id, type_id"

    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    scope_id = fields.Many2one('account.analytic.account', string='Scope', readonly=True)
    type_id = fields.Many2one('account.analytic.account', string='Type', readonly=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH ml_filtered AS (
                    SELECT
                        ml.id AS move_line_id,
                        m.partner_id,
                        m.company_id,
                        m.currency_id,
                        (ml.debit - ml.credit) AS ml_amount,
                        ml.analytic_distribution::jsonb AS dist
                    FROM account_move_line ml
                    JOIN account_move m ON m.id = ml.move_id
                    WHERE m.move_type = 'in_invoice'
                      AND m.state = 'posted'
                      AND ml.analytic_distribution IS NOT NULL
                      AND ml.analytic_distribution::text <> '{{}}'
                ),
                dist_keys AS (
                    SELECT
                        f.move_line_id,
                        f.partner_id,
                        f.company_id,
                        f.currency_id,
                        f.ml_amount,
                        kv.key AS key_combo,
                        (kv.value)::text::numeric AS pct
                    FROM ml_filtered f
                    CROSS JOIN LATERAL jsonb_each(f.dist) kv
                ),
                dist_accounts AS (
                    SELECT
                        d.move_line_id,
                        d.partner_id,
                        d.company_id,
                        d.currency_id,
                        d.ml_amount,
                        d.pct,
                        TRIM(part_str)::int AS account_id
                    FROM dist_keys d
                    CROSS JOIN LATERAL unnest(string_to_array(d.key_combo, ',')) AS part_str
                    WHERE TRIM(part_str) ~ '^[0-9]+$'
                ),
                classified AS (
                    SELECT
                        da.move_line_id,
                        da.partner_id,
                        da.company_id,
                        da.currency_id,
                        da.ml_amount,
                        da.pct,
                        da.account_id,
                        (p.is_project OR p.is_building OR p.is_unit) AS is_scope,
                        p.is_wip AS is_wip
                    FROM dist_accounts da
                    JOIN account_analytic_account aa ON aa.id = da.account_id
                    JOIN account_analytic_plan p ON p.id = aa.plan_id
                ),
                scope_parts AS (
                    SELECT move_line_id, partner_id, company_id, currency_id,
                           ml_amount, pct, account_id AS scope_id
                    FROM classified WHERE is_scope
                ),
                wip_parts AS (
                    SELECT DISTINCT move_line_id, account_id AS type_id
                    FROM classified WHERE is_wip
                ),
                pairs AS (
                    SELECT
                        s.partner_id AS vendor_id,
                        s.scope_id,
                        w.type_id,
                        s.company_id,
                        s.currency_id,
                        (s.ml_amount * s.pct / 100.0) AS amount
                    FROM scope_parts s
                    JOIN wip_parts w ON w.move_line_id = s.move_line_id
                )
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    vendor_id,
                    scope_id,
                    type_id,
                    company_id,
                    currency_id,
                    SUM(amount) AS amount
                FROM pairs
                GROUP BY vendor_id, scope_id, type_id, company_id, currency_id
            )
        """)