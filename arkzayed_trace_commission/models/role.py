from odoo import fields, models, tools


class TraceCommissionRole(models.Model):
    """The roles that can be picked to add everybody in that role at once."""
    _name = 'trace.commission.role'
    _description = 'Commission role'
    _auto = False
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW trace_commission_role AS (
                SELECT id AS id, name AS name FROM job_level
                UNION ALL SELECT 100001, 'Broker'
                UNION ALL SELECT 100002, 'Ambassador'
                UNION ALL SELECT 100003, 'Agent'
                UNION ALL SELECT 100004, 'Employee'
            )
        """)
