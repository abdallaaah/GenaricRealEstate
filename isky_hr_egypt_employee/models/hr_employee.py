# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from validate_email import validate_email
from odoo.exceptions import ValidationError
import datetime
import math


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    job_id = fields.Many2one('hr.job', string='Job Position')
    department_id = fields.Many2one('hr.department', string='Department')
    emp_no = fields.Char(string='Employee Code')
    employee_arabic_name = fields.Char(string='Arabic Name')
    sponsorship = fields.Selection(selection=[('company', 'Company'), ('organization', 'Organization'), ('none', 'None')],
                                   string='Sponsorship', default='none')
    is_manager = fields.Boolean(string='Manager?')
    education_ids = fields.One2many('exp.education.qualification', 'employee_id', string='Education Qualification')
    experience_ids = fields.One2many('exp.practical.experiences', 'employee_id', string='Practical Experience')
    training_ids = fields.One2many('exp.training', 'employee_id', string='Training')
    job_history_ids = fields.One2many('employee.job.history', 'employee_id', string='Job History')
    department_history_ids = fields.One2many('employee.department.history', 'employee_id', string='Department History')
    skill_ids = fields.One2many('exp.skills', 'employee_id', string='Skills')
    informant_ids = fields.One2many('exp.informants', 'employee_id', string='Referred By')
    first_hiring_date = fields.Date(string='Register Date')
    identification_source = fields.Char(string='Identification Source', translate=True)
    identification_issuance_date = fields.Date(string='Identification Issuing Date')
    identification_expire_date = fields.Date(string='Identification Expiry Date')
    passport_expire_date = fields.Date(string='Passport Expiry Date')
    qualification_id = fields.Many2one('exp.hr.qualification', string='Qualification')
    degree_id = fields.Many2one('hr.recruitment.degree', string='Degree')
    home_no = fields.Char(string='Home Phone')
    grade = fields.Char(string='Grade', translate=True)
    card_type_id = fields.Many2one('card.type', string='Card Type')
    licence_degree_id = fields.Many2one('licence.degree', string='Licence Degree')
    issuance_location_id = fields.Many2one('city.city', string='Issuance Location')
    issuance_date = fields.Date(string='Issuance Date')
    licence_location_id = fields.Many2one('city.city', string='Issuance Address')
    serviced_duration = fields.Integer(string='Serviced Duration', compute='calc_serviced_duration')
    passport_issue_place = fields.Many2one('res.country', string='Passport Issuing Country')
    passport_issue_date = fields.Date(string='Passport Issuing Date')
    identification_state = fields.Selection([('running', 'Running'), ('expired', 'Expired')], string='State',
                                            default='running', compute='calc_identification_state')
    licence_state = fields.Selection([('running', 'Running'), ('expired', 'Expired')], string='State',
                                     default='running', compute='calc_licence_state')
    have_license = fields.Selection([('no', 'No'), ('yes', 'Yes')], string='Have License ?', default='no')
    license_no = fields.Char(string='License No.')
    license_expiry_date = fields.Date(string='License Expiry Date')
    passport_expiry_date = fields.Date(string='Passport Expiry Date')
    medical_no = fields.Char(string='Medical NO.')
    medical_start_date = fields.Date(string='Medical Start Date')
    medical_end_date = fields.Date(string='Medical End Date')
    visa_medical_date = fields.Date(string='Visa Medical Date')
    contract_medical_date = fields.Date(string='Contract Medical Date')
    contract_medical_select = fields.Many2one('contract.medical.state', string='Contract Medical State')
    military_state = fields.Many2one('military.state', string='Military Status')
    religion = fields.Selection([('muslim', 'Muslim'), ('christian', 'Christian'), ('other', 'Other')],
                                string='Religion')
    last_name = fields.Char(string='Last Name')
    second_name = fields.Char(string='Second Name')
    employee_dependant_ids = fields.One2many('applicant.dependants', 'emp_id', 'Applicant Dependants')
    blood_type = fields.Selection(
        [('O-', 'O−'), ('O+', 'O+'), ('A-', 'A−'), ('A+', 'A+'), ('B-', 'B−'), ('B+', 'B+'), ('AB-', 'AB−'),
         ('AB+', 'AB+')], _('Blood Type'))

    passport_delivered = fields.Boolean(string='Employee Deliver Passport')
    medical_attachment_ids = fields.One2many('ir.attachment', 'employee_id', string='Medical Attachments')
    medical_result = fields.Selection([('yes', 'Fit'), ('no', 'UnFit')], string='Medical Exam Result')
    age = fields.Integer(string='Age', compute='get_employee_age')
    employee_status_id = fields.Many2one("employee.status", string="Employee Status")
    work_permit_ids = fields.One2many('work.permit', 'employee_id', string='Work Permit')
    full_name = fields.Char(compute='get_employee_full_name') 
    employment_type = fields.Selection(string="Employment Type",
                                       selection=[('daily_worker', 'Daily Worker'), ('worker', 'Worker'),
                                                  ('management', 'Management')])

    has_debt = fields.Boolean(string='Has Debt?')
    authority_license_ids = fields.One2many('authority.license', 'employee_id', string='Authority License')
    birthday_higri = fields.Char(string="Date of Birth(Higri)", required=False, compute='Gregorian2Hijri_birthday',
                                 readonly=True)
    address_home_id = fields.Many2one('res.partner', string='Address')
    hiring_date = fields.Date("Hiring Date")
    resignation_date = fields.Date()

    def intPart(self, floatNum):
        if floatNum < -0.0000001: return math.ceil(floatNum - 0.0000001)
        return math.floor(floatNum + 0.0000001)

    @api.depends('birthday')
    def Gregorian2Hijri_birthday(self):
        if self.birthday:
            year = fields.datetime.strptime(str(self.birthday), '%Y-%m-%d').year
            month = fields.datetime.strptime(str(self.birthday), '%Y-%m-%d').month
            day = fields.datetime.strptime(str(self.birthday), '%Y-%m-%d').day
            month_map = {1: {'name': 'Muh'},
                         2: {'name': 'Ṣaf'},
                         3: {'name': 'Rab1'},
                         4: {'name': 'Rab2'},
                         5: {'name': 'Jum1'},
                         6: {'name': 'Jum2'},
                         7: {'name': 'Raj'},
                         8: {'name': 'Sha'},
                         9: {'name': 'Ram'},
                         10: {'name': 'Shaw'},
                         11: {'name': 'DhuQ'},
                         12: {'name': 'DhuH'}}
            if ((year > 1582) or ((year == 1582) and (month > 10)) or \
                    ((year == 1582) and (month == 10) and (day > 14))):
                jd1 = self.intPart((1461 * (year + 4800 + self.intPart((month - 14) / 12.0))) / 4)
                jd2 = self.intPart((367 * (month - 2 - 12 * \
                                           (self.intPart((month - 14) / 12.0)))) / 12)
                jd3 = self.intPart((3 * (self.intPart((year + 4900 + \
                                                       self.intPart((month - 14) / 12.0)) / 100))) / 4)
                jd = jd1 + jd2 - jd3 + day - 32075

            else:
                jd1 = self.intPart((7 * (year + 5001 + \
                                         self.intPart((month - 9) / 7.0))) / 4)
                jd2 = self.intPart((275 * month) / 9.0)
                jd = 367 * year - jd1 + jd2 + day + 1729777

            l = jd - 1948440 + 10632
            n = self.intPart((l - 1) / 10631.0)
            l = l - 10631 * n + 354
            j1 = (self.intPart((10985 - l) / 5316.0)) * (self.intPart((50 * l) / 17719.0))
            j2 = (self.intPart(l / 5670.0)) * (self.intPart((43 * l) / 15238.0))
            j = j1 + j2
            l1 = (self.intPart((30 - j) / 15.0)) * (self.intPart((17719 * j) / 50.0))
            l2 = (self.intPart(j / 16.0)) * (self.intPart((15238 * j) / 43.0))
            l = l - l1 - l2 + 29
            m = self.intPart((24 * l) / 709.0)
            d = l - self.intPart((709 * m) / 24.0)
            y = 30 * n + j - 30
            self.birthday_higri = " %s  %s  %s " % (d, month_map[m]['name'], y)
        else:
            self.birthday_higri = ""

    _sql_constraints = [
        ('unique_emp_no', 'UNIQUE (emp_no)', "Employee Code Must Be Unique"),
        ('unique_identification_id', 'UNIQUE (identification_id)', "Identification No Must Be Unique"),
    ]

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|',
                      ('name', operator, name),
                      ('last_name', operator, name),
                      ('employee_arabic_name', operator, name),
                      ('emp_no', operator, name),
                      ]
        record_objs = self.search(domain + args, limit=limit)
        return record_objs.name_get()

    @api.depends('identification_expire_date')
    def calc_identification_state(self):
        for record in self:
            if record.identification_expire_date:
                today = (fields.Datetime.from_string(fields.Date.today())).date()
                identification_expire_date = (fields.Datetime.from_string(record.identification_expire_date)).date()
                no_of_days = ((today - identification_expire_date).days)
                record.identification_state = 'expired' if no_of_days > 0 else 'running'
            else:
                record.identification_state = 'expired'

    @api.depends('license_expiry_date')
    def calc_licence_state(self):
        for record in self:
            if record.license_expiry_date:
                today = (fields.Datetime.from_string(fields.Date.today())).date()
                license_expiry_date = (fields.Datetime.from_string(record.license_expiry_date)).date()
                no_of_days = (today - license_expiry_date).days
                record.licence_state = 'expired' if no_of_days > 0 else 'running'
            else:
                record.licence_state = 'expired'

    def check_expiration(self):
        today = (fields.Datetime.from_string(fields.Date.today())).date()
        for employee in self.search([]):
            # licence expiration
            if employee.license_expiry_date:
                license_expiry_date = (fields.Datetime.from_string(employee.license_expiry_date)).date()
                no_of_days = (today - license_expiry_date).days
                employee.licence_state = 'expired' if no_of_days > 0 else 'running'
                if no_of_days > 0:
                    # send notification to hr manager
                    partner_ids = []
                    for user in self.env['res.users'].sudo().search(
                            [('company_ids', '=', self.env.user.company_id.id)]):
                        if user.has_group('hr.group_hr_manager'):
                            partner_ids.append(user.partner_id.id)
                        body = (_(
                            "Licence Of %s has been expired.<br/>") % (
                                    employee.name))
                        employee.message_post(body=body, partner_ids=partner_ids)

            # identification expiration
            if employee.identification_expire_date:
                identification_expire_date = (fields.Datetime.from_string(employee.identification_expire_date)).date()
                no_of_days = ((today - identification_expire_date).days)
                employee.identification_state = 'expired' if no_of_days > 0 else 'running'
                if no_of_days > 0:
                    # send notification to hr manager
                    partner_ids = []
                    for user in self.env['res.users'].sudo().search(
                            [('company_ids', '=', self.env.user.company_id.id)]):
                        if user.has_group('hr.group_hr_manager'):
                            partner_ids.append(user.partner_id.id)
                        body = (_(
                            "Identification Of %s has been expired.<br/>") % (
                                    employee.name))
                        employee.message_post(body=body, partner_ids=partner_ids)

    @api.depends('first_hiring_date')
    def calc_serviced_duration(self):
        for record in self:
            if record.first_hiring_date:
                today = (fields.Datetime.from_string(fields.Date.today())).date()
                first_hiring_date = (fields.Datetime.from_string(record.first_hiring_date)).date()
                no_of_days = abs((today - first_hiring_date).days)
                record.serviced_duration = no_of_days
            else:
                record.serviced_duration = 0

    def write(self, vals):
        for employee in self:
            if 'job_id' in vals:
                self.env['employee.job.history'].create({
                    'employee_id': employee.id,
                    'job_id': employee.job_id.id,
                    'to_job_id': vals['job_id'],
                    'date': fields.Date.today(),
                })

            if 'department_id' in vals:
                self.env['employee.department.history'].create({
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id,
                    'to_department_id': vals['department_id'],
                    'date': fields.Date.today(),
                })
        return super(HrEmployee, self).write(vals)

    def get_employee_full_name(self):
        for record in self:
            record.full_name = ''
            if record.name:
                record.full_name += record.name
            if record.second_name:
                record.full_name += " " + record.second_name
            if record.last_name:
                record.full_name += " " + record.last_name

    def name_get(self):
        res = []
        for record in self:
            name = ''
            if record.name:
                name += str(record.name)
            if record.second_name:
                name += " " + str(record.second_name)
            if record.last_name:
                name += " " + str(record.last_name)
            if self.env.user.lang == 'ar_AA':
                name = str(record.employee_arabic_name) if record.employee_arabic_name else str(name)
            res.append((record.id, name))
        return res

    def get_employee_age(self):
        for rec in self:
            rec.age = 0
            if rec.birthday:
                current_year = datetime.datetime.now().year
                birth_date = rec.birthday
                current_age = current_year - birth_date.year
                rec.age = current_age

    @api.onchange('first_hiring_date')
    def get_employee_grade(self):
        for record in self:
            if record.first_hiring_date:
                today = (fields.Datetime.from_string(fields.Date.today())).date()
                first_hiring_date = (fields.Datetime.from_string(record.first_hiring_date)).date()
                no_of_days = abs((today - first_hiring_date).days)
                no_of_years = no_of_days / 365
                if no_of_years < 2:
                    record.grade = 'A'
                elif no_of_years >= 2 and no_of_years < 5:
                    record.grade = 'B'
                elif no_of_years >= 5 and no_of_years < 10:
                    record.grade = 'C'
                elif no_of_years >= 10:
                    record.grade = 'D'

    @api.constrains('work_email')
    def check_email(self):
        for record in self:
            if record.work_email:
                if validate_email(record.work_email) != True:
                    raise ValidationError(_("Please enter a valid email address on work email."))

    @api.constrains('birthday')
    def check_birth_date(self):
        for record in self:
            if record.birthday:
                if record.birthday >= fields.Date.today():
                    raise ValidationError(_("Birth date can't be greater than or equal current date!"))

    @api.constrains('identification_issuance_date', 'identification_expire_date')
    def check_identification_dates(self):
        for record in self:
            if record.identification_issuance_date and record.identification_expire_date:
                if record.identification_issuance_date > record.identification_expire_date:
                    raise ValidationError("Identification Issuing date must be less than identification expiry date!")

    @api.constrains('passport_issue_date', 'passport_expire_date')
    def check_passport_dates(self):
        for record in self:
            if record.passport_issue_date and record.passport_expire_date:
                if record.passport_issue_date > record.passport_expire_date:
                    raise ValidationError("Passport Issuing date must be less than passport expiry date!")

    @api.constrains('medical_start_date', 'medical_end_date')
    def check_medical_dates(self):
        for record in self:
            if record.medical_start_date and record.medical_end_date:
                if record.medical_start_date > record.medical_end_date:
                    raise ValidationError("Medical start date must be less than medical end date!")

    @api.constrains('license_expiry_date')
    def check_license_expiry_date(self):
        for record in self:
            if record.license_expiry_date:
                if record.license_expiry_date < fields.Date.today():
                    raise ValidationError("License expiry date must be greater than or equal current date!")

    @api.constrains('education_ids')
    def check_education_records(self):
        for rec in self:
            if rec.education_ids:
                for line in rec.education_ids:
                    education_line_ids = self.env['exp.education.qualification'].search(
                        [('employee_id', '=', rec.id),
                         ('name', '=', line.name),
                         ('qualification', '=', line.qualification), ('degree_date', '=', line.degree_date),
                         ('degree_rate', '=', line.degree_rate), ('full_rate', '=', line.full_rate),
                         ])
                    if education_line_ids:
                        if len(education_line_ids) > 1:
                            raise ValidationError(_('You add lines in education qualifications page with same data'))

    @api.constrains('experience_ids')
    def check_experience_records(self):
        for rec in self:
            if rec.experience_ids:
                for line in rec.experience_ids:
                    experience_ids = self.env['exp.practical.experiences'].search(
                        [('employee_id', '=', rec.id),
                         ('name', '=', line.name), ('business_sector', '=', line.business_sector),
                         ('job', '=', line.job), ('years', '=', line.years),
                         ])
                    if experience_ids:
                        if len(experience_ids) > 1:
                            raise ValidationError(_('You add lines in practical experience page with same data'))

    @api.constrains('training_ids')
    def check_training_records(self):
        for rec in self:
            if rec.training_ids:
                for line in rec.training_ids:
                    training_ids = self.env['exp.training'].search(
                        [('employee_id', '=', rec.id),
                         ('name', '=', line.name), ('institute', '=', line.institute),
                         ('duration', '=', line.duration), ('course_date', '=', line.course_date),
                         ])
                    if training_ids:
                        if len(training_ids) > 1:
                            raise ValidationError(_('You add lines in training page with same data'))

    @api.constrains('skill_ids')
    def check_skill_records(self):
        for rec in self:
            if rec.skill_ids:
                for line in rec.skill_ids:
                    skill_ids = self.env['exp.skills'].search(
                        [('employee_id', '=', rec.id),
                         ('name', '=', line.name), ('level', '=', line.level)
                         ])
                    if skill_ids:
                        if len(skill_ids) > 1:
                            raise ValidationError(_('You add lines in skills page with same data'))

    @api.constrains('informant_ids')
    def check_informant_records(self):
        for rec in self:
            if rec.informant_ids:
                for line in rec.informant_ids:
                    informant_ids = self.env['exp.informants'].search(
                        [('employee_id', '=', rec.id), ('email', '=', line.email),
                         ('name', '=', line.name), ('company', '=', line.company),
                         ('job', '=', line.job), ('mobile', '=', line.mobile),
                         ])
                    if informant_ids:
                        if len(informant_ids) > 1:
                            raise ValidationError(_('You add lines in referred page with same data'))
