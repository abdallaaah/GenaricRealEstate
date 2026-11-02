# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PracticalExperiences(models.Model):
    _name = 'exp.practical.experiences'
    _description = 'Practical Experiences'

    name = fields.Char(string='Company', required=True, translate=True)
    business_sector = fields.Char(string="Business Sector", required=True, translate=True)
    job = fields.Char(string="Job", required=True, translate=True)
    years = fields.Float(string="No. Of Years", required=True)
    applicant_id = fields.Many2one("hr.applicant", string="Applicant")
    employee_id = fields.Many2one("hr.employee", string="Employee")
