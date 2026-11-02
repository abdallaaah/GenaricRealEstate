from odoo import models, fields, api

class HrEmployeeInherit(models.Model):

    _inherit = 'hr.employee'

    is_duplicity_tracker = fields.Boolean()
    # attachment_line_ids = fields.One2many('attachment.type.line', 'hr_employee_id')
    director_id = fields.Many2one('res.users', compute='_get_team_users', string='Director')
    team_leader_id = fields.Many2one('res.users', compute="_get_team_users", string='Team Leader')
    sales_manager_id = fields.Many2one('res.users', compute="_get_team_users", string='Sales Manager')

    @api.depends('user_id')
    def _get_team_users(self):
        """Get team users for a given user based on job level."""
        user = self.user_id
        self.director_id = False
        self.team_leader_id = False
        self.sales_manager_id = False
        if user.job_level_id.is_sales_person:
            team = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1).crm_team_id
            if team:
                self.team_leader_id = team.user_id
                self.director_id = team.director_id
                self.sales_manager_id = team.sales_manager_id
        # elif user.job_level_id.is_team_leader:
        #     team = self.env['crm.team'].search([('user_id', '=', user.id)], limit=1)
        #     if team:
        #         self.director_id = team.director_id
        #         self.sales_manager_id = team.sales_manager_id
        elif user.job_level_id.is_sales_manager:
            team = self.env['crm.team'].search([('sales_manager_id', '=', user.id)], limit=1)
            if team:
                self.director_id = team.director_id