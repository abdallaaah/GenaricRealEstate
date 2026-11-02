# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import datetime
from odoo.exceptions import ValidationError

year = datetime.datetime.today().year
YEARS = [year - i for i in range(70)]

YEARS_LIST = []
for y in YEARS:
    YEARS_LIST.append((str(y), str(y)))


class EducationQualification(models.Model):
    _name = 'exp.education.qualification'
    _description = 'Education Qualification'

    name = fields.Char(string='Educational Institution', required=False, translate=True)
    qualification = fields.Char(string="Qualification", required=False, translate=True)
    degree_date = fields.Date(string="Degree Date", required=False)
    degree_year = fields.Selection(selection=YEARS_LIST, string="Degree Year", required=False)
    degree_rate = fields.Float(string="Degree Rate", required=False)
    full_rate = fields.Float(string='Full Rate', required=False)
    applicant_id = fields.Many2one("hr.applicant", string="Applicant")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    certificate_level = fields.Many2one('certificate.level', string='Certificate Level')

    @api.onchange('degree_date')
    def onchange_degree_date(self):
        if self.degree_date:
            try:
                self.degree_year = self.degree_date.year
            except:
                self.degree_year = False
        else:
            self.degree_year = False

    @api.constrains('degree_rate', 'full_rate')
    def check_rates(self):
        for rec in self:
            if rec.degree_rate > rec.full_rate:
                raise ValidationError(_('Degree rate must be less than full rate'))
