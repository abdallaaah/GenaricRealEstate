# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Skills(models.Model):
    _name = 'exp.skills'
    _description = 'Skills'

    name = fields.Char(string='Skill', required=True, translate=True)
    level = fields.Selection(selection=[
        ("beginner", "Beginner"),
        ("junior", "Junior"),
        ("senior", "Senior"),
        ("team_leader", "Team Leader")
    ], string='Level', required=True)
    applicant_id = fields.Many2one("hr.applicant", string="Applicant")
    employee_id = fields.Many2one("hr.employee", string="Employee")
