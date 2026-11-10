from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    job_level_id = fields.Many2one('job.level')
    sale_team_id = fields.Many2one('crm.team', string="Sales Team")
    user_department_id = fields.Many2one('hr.department', compute='_compute_user_department_id', store=True)

    @api.depends('employee_id.department_id')
    def _compute_user_department_id(self):
        for user in self:
            user.user_department_id = user.employee_id.department_id

    def _get_subordinate_users(self):
        """Everyone below these users in the sales reporting chain.

        The single accessor for the hierarchy: the commission engine resolves
        "whose deals roll up to this person" through broker.sales.hierarchy
        instead of re-deriving the chain from job-level flags. Returns the
        transitive closure, so a director gets the managers, leaders and
        members below them, and never the users passed in.
        """
        if not self:
            return self.browse()
        rows = self.env['broker.sales.hierarchy'].sudo().search_read(
            [('manager_id', 'in', self.ids)], ['subordinate_id'])
        subordinate_ids = {row['subordinate_id'][0] for row in rows if row['subordinate_id']}
        return self.browse(subordinate_ids - set(self.ids))
