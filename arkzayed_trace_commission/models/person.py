from odoo import fields, models, tools


class TraceCommissionPerson(models.Model):
    """Everyone who can earn a commission, in one searchable list: staff with commission records
    (sales person, directory, manager...), brokers, ambassadors, agents and employee claims."""
    _name = 'trace.commission.person'
    _description = 'Commission recipient'
    _auto = False
    _rec_name = 'label'
    _order = 'name'

    name = fields.Char(readonly=True)
    kind = fields.Char(string='Role', readonly=True)
    label = fields.Char(string='Name', readonly=True)
    source = fields.Selection([('user', 'Staff'), ('partner', 'Broker / Ambassador / Agent'), ('employee', 'Employee')],
                              readonly=True)
    source_id = fields.Integer(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW trace_commission_person AS (
                SELECT u.id AS id, p.name AS name,
                       string_agg(DISTINCT x.role, ', ') AS kind,
                       p.name || ' (' || string_agg(DISTINCT x.role, ', ') || ')' AS label,
                       'user' AS source, u.id AS source_id
                  FROM (
                        SELECT a.user_id AS uid, COALESCE(l.name, 'Sales Person') AS role
                          FROM realestate_commission_achievement a
                          LEFT JOIN job_level l ON l.id = a.job_level_id
                        UNION
                        SELECT user_id, 'Sales Person' FROM sale_proposal WHERE user_id IS NOT NULL
                  ) x
                  JOIN res_users u ON u.id = x.uid
                  JOIN res_partner p ON p.id = u.partner_id
                 GROUP BY u.id, p.name
                UNION ALL
                SELECT 1000000 + p.id AS id, p.name AS name,
                       string_agg(DISTINCT initcap(x.kind), ', ') AS kind,
                       p.name || ' (' || string_agg(DISTINCT initcap(x.kind), ', ') || ')' AS label,
                       'partner' AS source, p.id AS source_id
                  FROM (
                        SELECT broker_company AS pid, claim_type AS kind FROM broker_claim
                         WHERE claim_type IN ('broker', 'ambassador', 'agent') AND broker_company IS NOT NULL
                        UNION
                        SELECT referred_by_partner_id, referred_by FROM sale_proposal
                         WHERE referred_by_partner_id IS NOT NULL AND referred_by IN ('broker', 'ambassador')
                        UNION SELECT id, 'broker' FROM res_partner WHERE is_broker
                        UNION SELECT id, 'ambassador' FROM res_partner WHERE is_ambassador
                        UNION SELECT id, 'agent' FROM res_partner WHERE is_agent
                  ) x
                  JOIN res_partner p ON p.id = x.pid
                 GROUP BY p.id, p.name
                UNION ALL
                SELECT 2000000 + e.id AS id, e.name AS name,
                       'Employee' AS kind, e.name || ' (Employee)' AS label,
                       'employee' AS source, e.id AS source_id
                  FROM hr_employee e
                 WHERE e.id IN (SELECT employee_id FROM broker_claim WHERE claim_type = 'employee' AND employee_id IS NOT NULL)
            )
        """)
