from odoo import fields, models, tools

from ..models.commission_feature_codes import COMMISSION_FEATURE_TEAM_ROLLUP


class RealestateAchievementReport(models.Model):
    """Per-salesperson, per-target-period achievement summary, with team rollup.

    The rollup uses the same definition as the calculation: this query embeds
    ``broker.sales.hierarchy._hierarchy_sql()`` as a CTE. It deliberately does not
    JOIN the ``broker_sales_hierarchy`` view, because ``drop_view_if_exists`` cascades
    -- rebuilding the chain after a job.level change would otherwise drop this view
    with no error and leave the report broken until the next module upgrade.

    Rows start from plan assignments (sale.commission.plan.user x target period), not
    from achievements, so somebody who is on a plan but closed nothing themselves
    still gets a row. That matters precisely for the people the rollup is for: a
    director whose team sells but who books no deal personally would otherwise be
    absent from their own achievement report.

    ``own_achieved`` and ``team_achieved`` are reported separately so a figure can be
    traced; ``achieved`` is their sum. The team part honours the
    ``commission_team_rollup`` feature flag, with the same company-then-global
    precedence as :meth:`broker.feature.flag.is_feature_enabled`, so the report and
    the engine cannot disagree about what counts.
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
    own_achieved = fields.Monetary(
        currency_field='currency_id', readonly=True, string="Own Achieved",
        help="Volume from this person's own deals.")
    team_achieved = fields.Monetary(
        currency_field='currency_id', readonly=True, string="Team Achieved",
        help="Volume rolled up from everyone reporting to this person.")
    achieved = fields.Monetary(currency_field='currency_id', readonly=True)
    achieved_rate = fields.Float(readonly=True)
    tcr_count = fields.Float(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        Hierarchy = self.env['broker.sales.hierarchy']
        hierarchy_sql = Hierarchy._hierarchy_sql() or Hierarchy._EMPTY_SQL
        # Counts toward a person's target only if it is their own deal on a real-estate
        # target plan -- the same test _get_user_achieved_amount applies, so the report
        # and the engine agree. An achieve-plan row (a hierarchy beneficiary's override)
        # is commission, not achieved volume.
        counts_toward_target = """
            achievement.is_cancelled IS NOT TRUE
            AND EXISTS (
                SELECT 1 FROM sale_commission_plan counted_plan
                 WHERE counted_plan.id = achievement.commission_plan_id
                   AND counted_plan.realestate_commission IS TRUE
                   AND counted_plan.type = 'target')"""
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                WITH hierarchy AS (
            {hierarchy_sql}
                ), reporting_pair AS (
                    -- A manager/subordinate pair appears once per shared team; collapse it
                    -- or the join below would count that subordinate's volume twice.
                    SELECT DISTINCT manager_id, subordinate_id FROM hierarchy
                ), rollup_enabled AS (
                    SELECT
                        company.id AS company_id,
                        COALESCE(
                            (SELECT flag.enabled FROM broker_feature_flag flag
                              WHERE flag.code = '{COMMISSION_FEATURE_TEAM_ROLLUP}'
                                AND flag.company_id = company.id LIMIT 1),
                            (SELECT flag.enabled FROM broker_feature_flag flag
                              WHERE flag.code = '{COMMISSION_FEATURE_TEAM_ROLLUP}'
                                AND flag.company_id IS NULL LIMIT 1),
                            FALSE
                        ) AS enabled
                    FROM res_company company
                ), assignment AS (
                    SELECT
                        plan_user.user_id AS user_id,
                        target.id AS target_id,
                        target.plan_id AS plan_id,
                        target.date_from AS date_from,
                        target.date_to AS date_to,
                        target.amount AS target_amount,
                        -- Resolved the same way as the engine's _commission_company: where a
                        -- broker company is configured the rows were booked there, so matching
                        -- on the plan's own company would find none of them.
                        COALESCE(broker_company.currency_id, plan.currency_id) AS currency_id,
                        COALESCE(plan_company.commission_broker_company_id, plan_company.id)
                            AS company_id
                    FROM sale_commission_plan_target target
                    JOIN sale_commission_plan plan ON plan.id = target.plan_id
                    JOIN res_company plan_company ON plan_company.id = plan.company_id
                    LEFT JOIN res_company broker_company
                        ON broker_company.id = plan_company.commission_broker_company_id
                    JOIN sale_commission_plan_user plan_user ON plan_user.plan_id = plan.id
                        AND COALESCE(plan_user.date_from, target.date_from) <= target.date_to
                        AND COALESCE(plan_user.date_to, target.date_to) >= target.date_from
                    WHERE plan.realestate_commission IS TRUE
                      AND plan.type = 'target'
                ), own AS (
                    SELECT
                        assignment.user_id AS user_id,
                        assignment.target_id AS target_id,
                        assignment.plan_id AS plan_id,
                        assignment.date_from AS date_from,
                        assignment.date_to AS date_to,
                        assignment.target_amount AS target_amount,
                        assignment.currency_id AS currency_id,
                        assignment.company_id AS company_id,
                        COALESCE(SUM(achievement.sales_volume), 0) AS own_achieved,
                        COALESCE(SUM(
                            CASE WHEN line.is_tcr_sales_person THEN line.commission ELSE 0 END
                        ), 0) AS tcr_count
                    FROM assignment
                    LEFT JOIN realestate_commission_achievement achievement
                        ON achievement.user_id = assignment.user_id
                        AND achievement.company_id = assignment.company_id
                        AND {counts_toward_target}
                        AND EXISTS (
                            SELECT 1 FROM crm_lead lead
                             WHERE lead.id = achievement.opportunity_id
                               AND lead.achievement_date
                                   BETWEEN assignment.date_from AND assignment.date_to)
                    LEFT JOIN commission_commission line ON line.id = achievement.commission_line_id
                    GROUP BY
                        assignment.user_id, assignment.target_id, assignment.plan_id,
                        assignment.date_from, assignment.date_to, assignment.target_amount,
                        assignment.currency_id, assignment.company_id
                ), rolled AS (
                    -- Subordinates sit on their own plans, so their volume is matched by
                    -- the manager's period dates rather than by plan.
                    SELECT
                        own.user_id AS user_id,
                        own.target_id AS target_id,
                        SUM(achievement.sales_volume) AS team_achieved
                    FROM own
                    JOIN rollup_enabled ON rollup_enabled.company_id = own.company_id
                        AND rollup_enabled.enabled IS TRUE
                    JOIN reporting_pair ON reporting_pair.manager_id = own.user_id
                    JOIN realestate_commission_achievement achievement
                        ON achievement.user_id = reporting_pair.subordinate_id
                        AND achievement.company_id = own.company_id
                        AND {counts_toward_target}
                    JOIN crm_lead lead ON lead.id = achievement.opportunity_id
                        AND lead.achievement_date BETWEEN own.date_from AND own.date_to
                    GROUP BY own.user_id, own.target_id
                )
                SELECT
                    row_number() OVER () AS id,
                    own.user_id AS user_id,
                    team.id AS team_id,
                    own.plan_id AS commission_plan_id,
                    own.date_from AS date_from,
                    own.date_to AS date_to,
                    own.target_amount AS target_amount,
                    own.own_achieved AS own_achieved,
                    COALESCE(rolled.team_achieved, 0) AS team_achieved,
                    own.own_achieved + COALESCE(rolled.team_achieved, 0) AS achieved,
                    CASE
                        WHEN own.target_amount > 0
                        THEN (own.own_achieved + COALESCE(rolled.team_achieved, 0))
                             / own.target_amount
                        ELSE 0
                    END AS achieved_rate,
                    own.tcr_count AS tcr_count,
                    own.currency_id AS currency_id,
                    own.company_id AS company_id
                FROM own
                LEFT JOIN rolled
                    ON rolled.user_id = own.user_id AND rolled.target_id = own.target_id
                -- res_users.sale_team_id rather than crm_team_member: single-valued, so a
                -- person on two teams cannot duplicate their own row.
                LEFT JOIN res_users reporting_user ON reporting_user.id = own.user_id
                LEFT JOIN crm_team team ON team.id = reporting_user.sale_team_id
            )
        """)
