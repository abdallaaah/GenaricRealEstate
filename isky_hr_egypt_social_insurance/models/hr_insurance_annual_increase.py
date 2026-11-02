# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrInsuranceAnnualIncrease(models.Model):
    _name = 'hr.insurance.annual.increase'
    _description = 'Insurance Annual Increase'
    _rec_name = 'annual_insurance_sequence'

    state = fields.Selection([('draft', "Draft"), ('submitted', "Submitted")], default='draft', string="Status")
    percentage = fields.Float(string='Percentage')
    annual_insurance_sequence = fields.Char(string='Sequence')
    annual_date = fields.Date(string='Date', default=fields.Date.context_today)
    annual_insurance_line_ids = fields.One2many('insurance.annual.increase.line', 'annual_insurance_id', copy=True)
    employee_ids = fields.Many2many('hr.employee', string='Employees')

    @api.model
    def create(self, vals):
        if vals:
            vals['annual_insurance_sequence'] = self.env['ir.sequence'].next_by_code('hr.insurance.annual.sequence')
        return super(HrInsuranceAnnualIncrease, self).create(vals)

    def action_submit(self):
        for rec in self:
            if not rec.employee_ids:
                raise ValidationError("You need to  add employees")
            rec.state = 'submitted'
            new_social_insurance = self.env['hr.insurance'].create({'insurance_date': rec.annual_date})
            for ins_line in rec.annual_insurance_line_ids:
                if ins_line.new_social_amount > 0.0:
                    new_insurance_line = ins_line.insurance_line_id.copy()
                    new_insurance_line.insurance_id = new_social_insurance.id
                    new_insurance_line.insurance_date = rec.annual_date
                    new_insurance_line.subscription = ins_line.new_social_amount
                    new_insurance_line.get_insurance_values()
            if new_social_insurance.insurance_line_ids:
                new_social_insurance.action_submit()

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError("Only Draft Insurance Can Be Deleted!")
            else:
                return super(HrInsuranceAnnualIncrease, self).unlink()

    @api.constrains('employee_ids', 'percentage')
    def fill_employee_data(self):
        for record in self:
            record.annual_insurance_line_ids = [(6, 0, [])]
            for employee in record.employee_ids:
                insurance_line = self.env['insurance.line'].search([('employee_id', '=', employee.id)],
                                                                   order='insurance_date desc', limit=1)
                if insurance_line:
                    annual_line = self.env['insurance.annual.increase.line'].create({'annual_insurance_id': record.id,
                                                                                     'insurance_line_id': insurance_line.id,
                                                                                     'annual_date': record.annual_date})
                    annual_line.set_new_social_amount()


class HrInsuranceAnnualIncreaseLine(models.Model):
    _name = 'insurance.annual.increase.line'
    _description = 'Annual Increase Line'

    annual_insurance_id = fields.Many2one('hr.insurance.annual.increase', string='Annual Increase')
    insurance_line_id = fields.Many2one('insurance.line')
    employee_id = fields.Many2one('hr.employee', related='insurance_line_id.employee_id', string='Employee')
    old_social_amount = fields.Float(string='Old Social Amount', related='insurance_line_id.subscription')
    new_social_amount = fields.Float(string='New Social Amount')
    annual_date = fields.Date(string='Date', default=fields.Date.context_today)

    def set_new_social_amount(self):
        for record in self:
            if record.annual_insurance_id and record.annual_insurance_id.percentage and record.old_social_amount:
                record.new_social_amount = record.old_social_amount + (
                        (record.annual_insurance_id.percentage * record.old_social_amount) / 100.0)
