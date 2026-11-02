# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrJob(models.Model):
    _inherit = 'hr.job'

    structure_id = fields.Many2one('hr.payroll.structure', string='Salary Structure')
    duties = fields.Char(string='Duties')
    equipment = fields.Char(string='Equipment')
    span_of_control = fields.Char(string='Span Of Control')
    job_summary = fields.Char(string='Job Summary')
    responsibilities = fields.Char(string='Responsibilities')
    conditions = fields.Char(string='Conditions')
    knowledge = fields.Char(string='Knowledg')
    experience = fields.Char(string='Experience')
    skills = fields.Char(string='Skills')
    attitudes = fields.Char(string='Attitudes')
    abilities = fields.Char(string='Abilities')
    competences = fields.Char(string='Competences')
    parent_department_id = fields.Many2one('hr.department', related='department_id.parent_id',
                                           string='Parent Department')
