# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class EmployeeJobHistory(models.Model):
    _name = "employee.job.history"
    _description = 'Employee Job History'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    job_id = fields.Many2one('hr.job', string='Job')
    to_job_id = fields.Many2one('hr.job', string='Job')
    date = fields.Date(string='Date')
