# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    sale_team_id = fields.Many2one('crm.team', string='Sales Team')
    user_department_id = fields.Many2one('hr.department', compute="_compute_department_id", store=True)

    job_level_id = fields.Many2one('job.level')

    @api.depends('employee_id', 'employee_id.department_id')
    def _compute_department_id(self):
        for user in self:
            user.user_department_id = user.employee_id.department_id

    def _compute_sale_team(self):
        for user in self:
            teams = self.env['crm.team'].search([('member_ids', 'in', [user.id])])
            user.sale_team_id = teams[0].id if teams else False
