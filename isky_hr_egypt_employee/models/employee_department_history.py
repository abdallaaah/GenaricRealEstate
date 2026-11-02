# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class EmployeeDepartmentHistory(models.Model):
    _name = "employee.department.history"
    _description = 'Employee Department History'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    department_id = fields.Many2one('hr.department', string='Department')
    to_department_id = fields.Many2one('hr.department', string='Department')
    date = fields.Date(string='Date')
