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
