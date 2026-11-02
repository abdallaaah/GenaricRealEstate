# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo import fields, models, api, _


class ApplicantDependants(models.Model):
    _name = 'applicant.dependants'
    _description = 'Applicant Dependants'

    name = fields.Char(string='Name', required=True, translate=True)
    english_name = fields.Char(string='English Name', translate=True)
    military_state = fields.Many2one('military.state', string='Military Status')
    # iqama_number = fields.Char(string='Iqama Number')
    gender = fields.Selection(selection=[('male', 'Male'), ('female', 'Female')], string='Gender')
    relation = fields.Selection(selection=[('spouse', 'Spouse'), ('child', 'Child')], string='Relation')
    age = fields.Integer(string='Age', compute='calc_dependant_age')
    remarks = fields.Text(string='Remarks', translate=True)
    country_id = fields.Many2one('res.country', string='Nationality')
    emp_id = fields.Many2one('hr.employee', string='Employee')
    passport_no = fields.Char(string='Passport No.')
    passport_issue_date = fields.Date(string='Passport Issuing Date')
    passport_expiry_date = fields.Date(string='Passport Expiry Date')
    birth_date = fields.Date(string='Date Of Birth')
    tickets_allowed = fields.Boolean(string='Tickets allowed?')
    fees = fields.Float(string='Fees')
    date = fields.Date(string='Date')

    @api.constrains('passport_issue_date', 'passport_expiry_date')
    def check_passport_dates(self):
        for rec in self:
            if rec.passport_issue_date and rec.passport_expiry_date:
                if rec.passport_expiry_date <= rec.passport_issue_date:
                    raise ValidationError(_('Passport expiry date must be larger than passport Issuing date'))

    @api.constrains('birth_date')
    def check_birth_date(self):
        for record in self:
            if record.birth_date:
                if record.birth_date >= fields.Date.today():
                    raise ValidationError(_("Birth date can't be greater than or equal current date!"))

    @api.depends('birth_date')
    def calc_dependant_age(self):
        for record in self:
            record.age = 0
            if record.birth_date:
                today = (fields.Datetime.from_string(fields.Date.today())).date()
                birth_date = (fields.Datetime.from_string(record.birth_date)).date()
                no_of_days = abs((today - birth_date).days)
                record.age = int(no_of_days / 365.0)
