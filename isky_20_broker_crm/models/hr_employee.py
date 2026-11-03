from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_duplicity_tracker = fields.Boolean(
        help="Leads with a phone number matching an existing lead are reassigned to this "
             "employee's user instead of the salesperson who created them.")
    director_id = fields.Many2one('res.users', compute='_compute_team_hierarchy', string="Director")
    team_leader_id = fields.Many2one('res.users', compute='_compute_team_hierarchy', string="Team Leader")
    sales_manager_id = fields.Many2one('res.users', compute='_compute_team_hierarchy', string="Sales Manager")

    @api.depends('user_id', 'user_id.job_level_id')
    def _compute_team_hierarchy(self):
        for employee in self:
            employee.director_id = False
            employee.team_leader_id = False
            employee.sales_manager_id = False
            user = employee.user_id
            if not user:
                continue
            if user.job_level_id.is_sales_person:
                member = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1)
                team = member.crm_team_id
            elif user.job_level_id.is_team_leader:
                team = self.env['crm.team'].search([('user_id', '=', user.id)], limit=1)
            elif user.job_level_id.is_sales_manager:
                team = self.env['crm.team'].search([('sales_manager_id', '=', user.id)], limit=1)
            else:
                team = self.env['crm.team']
            if team:
                employee.team_leader_id = team.user_id
                employee.director_id = team.director_id
                employee.sales_manager_id = team.sales_manager_id
