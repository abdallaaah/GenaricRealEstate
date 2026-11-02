# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from validate_email import validate_email


class Informants(models.Model):
    _name = 'exp.informants'
    _description = 'Informants'

    name = fields.Char(string='Name', required=True, translate=True)
    company = fields.Char(string="Company", required=True, translate=True)
    job = fields.Char(string="Job", required=True, translate=True)
    mobile = fields.Char(string="Mobile", required=True)
    email = fields.Char(string="Email", required=True)
    applicant_id = fields.Many2one("hr.applicant", string="Applicant")
    employee_id = fields.Many2one("hr.employee", string="Employee")

    @api.constrains("email")
    def _check_email(self):
        for record in self:
            if record.email:
                if not validate_email(record.email):
                    raise ValidationError(_("Please enter a valid email address in referred by"))
