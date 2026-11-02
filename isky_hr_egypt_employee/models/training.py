# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Training(models.Model):
    _name = 'exp.training'
    _rec_name='course_id'
    _description = "Partner Training"

    # name = fields.Char(string='Course', required=True)
    course_id = fields.Many2one(comodel_name="exp.course", string="Course")
    institute_id = fields.Many2one(comodel_name="exp.institute",string="Institute/Organization", required=True)
    duration = fields.Char(string="Duration", required=True)
    course_date = fields.Date(string="Date", required=True)
    applicant_id = fields.Many2one("hr.applicant", string="Applicant")
    employee_id = fields.Many2one("hr.employee", string="Employee")
    cost = fields.Float(string="", required=False, )
    start_date = fields.Date(string="Start Date", required=False, )
    completion_rate = fields.Float(string="Completion rate", required=False, )
    type_id = fields.Many2one(comodel_name="training.type", string="Type", required=False, )
    categ_id = fields.Many2one(comodel_name="training.category", string="Category", required=False, )

    @api.constrains('course_date')
    def check_course_date(self):
        for record in self:
            if record.course_date:
                if record.course_date >= fields.Date.today():
                    raise ValidationError("Training date must be less current date!")


class TrainingType(models.Model):
    _name = 'training.type'
    _rec_name = 'name'
    _description = 'Training Type'

    name = fields.Char(translate=True)


class TrainingCategory(models.Model):
    _name = 'training.category'
    _rec_name = 'name'
    _description = 'Training Category'

    name = fields.Char(translate=True)


class Course(models.Model):
    _name = 'exp.course'
    _rec_name = 'name'
    _description = 'Courses'

    name = fields.Char(translate=True)


class Institute(models.Model):
    _name = 'exp.institute'
    _rec_name = 'name'
    _description = 'Institutes'

    name = fields.Char(translate=True)
