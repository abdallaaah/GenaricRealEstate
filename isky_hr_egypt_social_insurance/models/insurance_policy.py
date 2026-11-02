# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InsurancePolicy(models.Model):
    _name = 'insurance.policy'
    _description = 'Insurance Policy'

    name = fields.Char(string="Description")
    employee_percentage = fields.Float(string='Employee Percentage')
    company_percentage = fields.Float(string='Company Percentage')
    policy_date = fields.Date(string='Policy Date')
    fixed_amount = fields.Boolean(string='Fixed?', default=True)
    salary_rule_ids = fields.Many2many('hr.salary.rule', string='Rules')

    @api.constrains('employee_percentage', 'company_percentage')
    def check_percentages(self):
        for policy in self:
            if policy.employee_percentage <= 0 and policy.fixed_amount:
                raise ValidationError("Employee Percentage should be greater than zero!")
            if policy.employee_percentage >= 100:
                raise ValidationError("Employee Percentage should be less than 100% !!")

            # if policy.company_percentage <= 0 and policy.fixed_amount:
            #     raise ValidationError("Company Percentage should be greater than zero!")
            if policy.company_percentage >= 100:
                raise ValidationError("Company Percentage should be less than 100% !!")
