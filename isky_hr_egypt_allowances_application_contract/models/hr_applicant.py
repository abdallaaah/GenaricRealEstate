# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
from validate_email import validate_email


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    contract_created = fields.Boolean(string='Contract Created', copy=False)
    department_id = fields.Many2one('hr.department', string='Department')
    contract_id = fields.Many2one('hr.contract', string='contract')
    job_id = fields.Many2one("hr.job", string='Applied Job', required=True)
    refused_reason = fields.Text(string="Refused Reason")
    salary_proposed = fields.Float(string='Job Salary')
    nationality_id = fields.Many2one('res.country', string='Nationality')
    gender = fields.Selection(selection=[('male', 'Male'), ('female', 'Female')], string='Gender')
    birthday = fields.Date(string='Date of Birth')
    app_contract_proposal = fields.Boolean(related='stage_id.contract_proposal')
    first_hiring_date = fields.Date(string='Register Date')
    structure_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', related='job_id.structure_id',
                                   required=True)
    emp_id = fields.Many2one('hr.employee', string="Employee", track_visibility="onchange",
                             help="Employee linked to the applicant.", copy=False)
    notes = fields.Text(string="Notes")


    @api.constrains("email_from")
    def check_partner_email(self):
        for record in self:
            if record.email_from:
                if not validate_email(record.email_from):
                    raise ValidationError("Please enter a valid email address for applicant")

    @api.constrains('birthday')
    def check_birth_date(self):
        for record in self:
            if record.birthday:
                if record.birthday >= fields.Date.today():
                    raise ValidationError("Birth date can't be greater than or equal current date!")

    @api.constrains('availability')
    def check_availability(self):
        for record in self:
            if record.availability:
                if record.availability < fields.Date.today():
                    raise ValidationError("Availability date must be greater than or equal current date!")

    @api.constrains('salary_proposed')
    def check_salary_proposed_value(self):
        for record in self:
            if record.salary_proposed <= 0:
                raise ValidationError("Job salary must be greater than zero!")

    @api.constrains('date_action')
    def check_date_action(self):
        for record in self:
            if record.date_action:
                if record.date_action < fields.Date.today():
                    raise ValidationError("Action date must be greater than or equal current date!")

    def create_employee_from_applicant(self):
        for record in self:
            hr_employee = self.env['hr.employee']
            contact_name = False
            if record.partner_id:
                contact_name = record.partner_id.display_name
            if record.partner_name or contact_name:
                emp_id = hr_employee.create({'name': record.partner_name or contact_name,
                                             'job_id': record.job_id.id,
                                             'birthday': record.birthday,
                                             'country_id': record.nationality_id.id,
                                             'department_id': record.department_id.id,
                                             'work_email': record.email_from,
                                             'work_phone': record.partner_phone or False,
                                             'mobile_phone': record.partner_mobile,
                                             'gender': record.gender,
                                             'first_hiring_date': record.first_hiring_date,
                                             })
                record.emp_id = emp_id.id
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'hr.employee',
                    'view_mode': 'form',
                    'res_id': emp_id.id,
                    'target': 'current'
                }
            else:
                raise ValidationError('Please enter applicant name')

    def create_contract_from_applicant(self):
        for record in self:
            hr_contract = self.env['hr.contract']
            if record.emp_id and record.first_hiring_date and record.structure_id and record.salary_proposed:
                contract_id = hr_contract.create({'name': str(record.emp_id.name) + ' contract',
                                                  'employee_id': record.emp_id.id,
                                                  'department_id': record.department_id.id,
                                                  'job_id': record.job_id.id,
                                                  'wage': record.salary_proposed,
                                                  'structure_type_id': record.structure_id.type_id.id,
                                                  'date_start': record.first_hiring_date,
                                                  })
                record.contract_created = True
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'hr.contract',
                    'view_mode': 'form',
                    'res_id': contract_id.id,
                    'target': 'current'
                }
