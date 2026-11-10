from odoo import api, fields, models, tools
from odoo.tools.sql import table_exists

MEMBER_SLOT = 'member_ids'


class BrokerSalesHierarchy(models.Model):
    """Who reports to whom in the sales organisation, derived from job.level's chain.

    This exists because the reporting chain used to be written twice, by hand, and the
    two copies disagreed: the commission engine had a four-branch ``if/elif`` over
    job-level flags, while the achievement report had six hand-written ``UNION``
    branches plus a recursive CTE. Neither covered the same cases.

    Here the relationships are generated from ``job.level.hierarchy_sequence`` /
    ``team_role_field``, so there is one definition. A manager is linked to a
    subordinate when the subordinate sits in a lower-ranked slot on the same sales
    team **and every slot between them is vacant** -- which is what makes a director
    manage the team leader directly on a team that has no sales manager, without that
    case being spelled out anywhere. The rows are the transitive closure, so a
    director's subordinates include the managers, leaders, and members below them.
    """
    _name = 'broker.sales.hierarchy'
    _description = "Broker Sales Reporting Hierarchy"
    _auto = False
    _order = 'manager_id, depth, subordinate_id'

    manager_id = fields.Many2one('res.users', readonly=True)
    subordinate_id = fields.Many2one('res.users', readonly=True)
    team_id = fields.Many2one('crm.team', readonly=True)
    depth = fields.Integer(readonly=True, help="Number of chain steps between the two people.")

    # -------------------------------------------------------------- SQL generation

    @api.model
    def _slot_sql(self, level, alias):
        """For one chain slot: (join fragment, user-id expression, occupied condition).

        Everything is expressed relative to a ``crm_team ct`` in the caller's FROM.
        """
        slot = level.team_role_field
        if slot == MEMBER_SLOT:
            join = (f"JOIN crm_team_member {alias} "
                    f"ON {alias}.crm_team_id = ct.id AND {alias}.active IS TRUE")
            return join, f"{alias}.user_id", f"{alias}.user_id IS NOT NULL"
        return "", f"ct.{slot}", f"ct.{slot} IS NOT NULL"

    @api.model
    def _slot_vacant_sql(self, level):
        """Condition that nobody occupies this slot on the team -- the skip-level test."""
        slot = level.team_role_field
        if slot == MEMBER_SLOT:
            return ("NOT EXISTS (SELECT 1 FROM crm_team_member vacancy "
                    "WHERE vacancy.crm_team_id = ct.id AND vacancy.active IS TRUE)")
        return f"ct.{slot} IS NULL"

    @api.model
    def _hierarchy_sql(self):
        """The hierarchy query, or None when no chain is configured yet.

        Returned as a string so both this view and the commission achievement report
        can use it. The report embeds it as a CTE rather than joining this view,
        because ``drop_view_if_exists`` cascades -- rebuilding the chain would
        otherwise silently drop any view that depended on it.
        """
        if not table_exists(self.env.cr, 'job_level'):
            # Model init order during a fresh install can reach this view before
            # job.level's own table exists.
            return None
        chain = self.env['job.level']._get_hierarchy_chain()
        if len(chain) < 2:
            return None

        valid_slots = {value for value, _label in self.env['job.level']._fields['team_role_field'].selection}
        branches = []
        for higher_index, higher in enumerate(chain):
            for lower_index in range(higher_index):
                lower = chain[lower_index]
                # team_role_field is a Selection, but this value is interpolated straight
                # into DDL, so refuse anything that is not a known slot.
                if higher.team_role_field not in valid_slots or lower.team_role_field not in valid_slots:
                    continue
                suffix = f"{higher_index}_{lower_index}"
                higher_join, higher_user, higher_ok = self._slot_sql(higher, f"mgr_{suffix}")
                lower_join, lower_user, lower_ok = self._slot_sql(lower, f"sub_{suffix}")
                conditions = [higher_ok, lower_ok, f"{higher_user} <> {lower_user}"]
                conditions += [
                    self._slot_vacant_sql(chain[between])
                    for between in range(lower_index + 1, higher_index)
                ]
                branches.append(f"""
        SELECT DISTINCT
            {higher_user} AS manager_id,
            {lower_user} AS subordinate_id,
            ct.id AS team_id
        FROM crm_team ct
        {higher_join}
        {lower_join}
        WHERE {' AND '.join(conditions)}""")

        if not branches:
            return None

        return f"""
WITH RECURSIVE direct_report AS (
{' UNION ALL '.join(branches)}
), reporting_closure AS (
        SELECT manager_id, subordinate_id, team_id, 1 AS depth
        FROM direct_report
    UNION ALL
        SELECT closure.manager_id, direct_report.subordinate_id, direct_report.team_id, closure.depth + 1
        FROM reporting_closure closure
        JOIN direct_report ON direct_report.manager_id = closure.subordinate_id
        WHERE closure.depth < {len(chain)}
)
SELECT
    row_number() OVER () AS id,
    manager_id,
    subordinate_id,
    team_id,
    MIN(depth) AS depth
FROM reporting_closure
WHERE manager_id <> subordinate_id
GROUP BY manager_id, subordinate_id, team_id"""

    _EMPTY_SQL = """
SELECT
    0 AS id,
    NULL::integer AS manager_id,
    NULL::integer AS subordinate_id,
    NULL::integer AS team_id,
    0 AS depth
WHERE FALSE"""

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Falls back to a valid empty view: on a fresh install this runs before
        # data/job_level_data.xml has loaded, so there is no chain to generate from yet.
        # The post-init hook and job.level's own create/write rebuild it afterwards --
        # without that, the rollup returns nothing and reports no error.
        query = self._hierarchy_sql() or self._EMPTY_SQL
        self.env.cr.execute(f"CREATE VIEW {self._table} AS ({query})")

    @api.model
    def _rebuild(self):
        """Regenerate the view after the job.level chain changes."""
        self.init()
