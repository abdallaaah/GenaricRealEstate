from odoo import fields, models, tools


class RealestateAchievementReport(models.Model):
    """Per-salesperson, per-target-period achievement summary.

    Simpler than the v17 recursive-CTE version: each row is one person's own
    achieved amount and TCR count for one target period. Team-leader/manager
    roll-up for the person's own bracket rate already happens at calculation
    time (RealestateCommissionAchievement._get_user_achieved_amount`); this
    report does not additionally roll figures up for display, which the v17
    report did. Noted as a deliberate scope reduction, not an oversight.
    """
    _name = 'realestate.achievement.report'
    _description = "Real Estate Commission Achievement Report"
    _auto = False
    _order = 'date_to desc'

    user_id = fields.Many2one('res.users', readonly=True)
    team_id = fields.Many2one('crm.team', readonly=True)
    commission_plan_id = fields.Many2one('sale.commission.plan', readonly=True)
    date_from = fields.Date(readonly=True)
    date_to = fields.Date(readonly=True)
    target_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    achieved = fields.Monetary(currency_field='currency_id', readonly=True)
    achieved_rate = fields.Float(readonly=True)
    tcr_count = fields.Float(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT
                    row_number() OVER () AS id,
                    a.user_id AS user_id,
                    team.id AS team_id,
                    t.plan_id AS commission_plan_id,
                    t.date_from AS date_from,
                    t.date_to AS date_to,
                    t.amount AS target_amount,
                    SUM(a.sales_volume) AS achieved,
                    CASE WHEN t.amount > 0 THEN SUM(a.sales_volume) / t.amount ELSE 0 END AS achieved_rate,
                    SUM(CASE WHEN cc.is_tcr_sales_person THEN cc.commission ELSE 0 END) AS tcr_count,
                    p.currency_id AS currency_id,
                    p.company_id AS company_id
                FROM realestate_commission_achievement a
                JOIN sale_commission_plan p ON p.id = a.commission_plan_id
                JOIN sale_commission_plan_target t ON t.plan_id = p.id
                JOIN crm_lead lead ON lead.id = a.opportunity_id
                    AND lead.achievement_date BETWEEN t.date_from AND t.date_to
                LEFT JOIN commission_commission cc ON cc.id = a.commission_line_id
                LEFT JOIN crm_team_member tm ON tm.user_id = a.user_id
                LEFT JOIN crm_team team ON team.id = tm.crm_team_id
                WHERE p.realestate_commission IS TRUE
                GROUP BY a.user_id, team.id, t.plan_id, t.date_from, t.date_to, t.amount, p.currency_id, p.company_id
            )
        """)
