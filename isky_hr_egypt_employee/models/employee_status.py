# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class EmployeeStatus(models.Model):
    _name = "employee.status"
    _description = 'Employee Status'

    name = fields.Char(string='Status', required=1, translate=True)
