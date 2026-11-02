# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from num2words import num2words
from odoo.exceptions import ValidationError
import math


class HrContract(models.Model):
    _inherit = "hr.contract"

    @api.depends("wage")
    def wage_words_value(self):
        for line in self:
            if line.wage:
                if str(self.env.user.lang)[:2] == "ar":
                    words = num2words(int(abs(line.wage)), lang='ar')
                    if line.wage - int(line.wage):
                        words += " - " + num2words(str(abs(int((line.wage - int(line.wage)) * 100))), lang='ar')
                    line.wage_amount_words = words
                else:
                    line.wage_amount_words = num2words(line.wage, lang='en')
            else:
                line.wage_amount_words = ""

    housing = fields.Float(string='Housing (Monthly)', help='Monthly Housing Amount', track_visibility='onchange')
    housing_amount = fields.Float(string='Housing Amount', help='Monthly Housing Amount',
                                  compute='_get_amount', track_visibility='onchange')
    transportation = fields.Float(string='Transportation (Monthly)', help='Monthly Transportation Amount',
                                  track_visibility='onchange')
    transportation_amount = fields.Float(string='Transportation Amount (Monthly)', help='Monthly Transportation Amount',
                                         compute='_get_amount', track_visibility='onchange')
    natural_work = fields.Float(string='Natural Work (Monthly)', help='Monthly Natural Work Amount',
                                track_visibility='onchange')
    natural_work_amount = fields.Float(string='Natural Work Amount (Monthly)', help='Monthly Natural Work Amount',
                                       compute='_get_amount', track_visibility='onchange')
    food_allowance = fields.Float(string='Food (Monthly)', help='Monthly Food Amount', track_visibility='onchange')
    food_allowance_amount = fields.Float(string='Food Amount (Monthly)', help='Monthly Food Amount',
                                         compute='_get_amount', track_visibility='onchange')
    mobile_allowance = fields.Float(string='Mobile (Monthly)', help='Monthly Mobile Amount',
                                    track_visibility='onchange')
    mobile_allowance_amount = fields.Float(string='Mobile Amount (Monthly)', help='Monthly Mobile Amount',
                                           compute='_get_amount', track_visibility='onchange')
    mobile_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                             string='Mobile Type',
                                             default='amount', track_visibility='onchange')
    house_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                            string='House Type',
                                            default='amount', track_visibility='onchange')
    transportation_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                                     string='Transportation Type', default='amount',
                                                     track_visibility='onchange')
    natural_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                              string='Natural Work Type',
                                              default='amount', track_visibility='onchange')
    food_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                           string='Food Type',
                                           default='amount', track_visibility='onchange')
    car_allowance = fields.Float('Car (Monthly)', help='Monthly Car Amount', track_visibility='onchange')
    car_allowance_amount = fields.Float(string='Car Amount (Monthly)', help='Monthly Car Amount',
                                        compute='_get_amount', track_visibility='onchange')
    car_allowance_type = fields.Selection(selection=[('amount', 'Amount'), ('percentage', 'Percentage')],
                                          string='Car Type',
                                          default='amount', track_visibility='onchange')

    is_egyptian = fields.Boolean(string='Egyptian', related="employee_id.is_egyptian")
    contract_period = fields.Selection(selection=[('three_month', 'Three Months'), ('six_month', 'Six Months'),
                                                  ('one_year', 'One Year'), ('two_year', 'Two Year'),
                                                  ('unlimited', 'Unlimited Contract')], string="Contract Period")
    with_accommodation = fields.Boolean(string='With Accommodation', track_visibility='onchange')
    house_periodic = fields.Boolean(string='Periodic')
    house_number_of_months = fields.Integer(string='NO.Of Months', default=1)
    house_date = fields.Date(string='Housing Date')
    resource_calendar_id = fields.Many2one(
        'resource.calendar', 'Working Schedule',
        default=lambda self: self.env.company.resource_calendar_id.id, copy=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", track_visibility='onchange')
    date_start = fields.Date('Start Date', required=True, default=fields.Date.today,
                             help="Start date of the contract.", track_visibility='onchange')
    date_end = fields.Date('End Date',
                           help="End date of the contract (if it's a fixed-term contract).",
                           track_visibility='onchange')
    general_terms = fields.Text(string='General Terms')
    wage_amount_words = fields.Char(compute="wage_words_value", string='Wage in Words')
    employee_policy_id = fields.Many2one('policy.group', 'Policy Group', track_visibility='onchange')
    work_type = fields.Selection(
        selection=[('full', 'Full'), ('partial', 'Partial'), ('half', 'Half'), ('exempt', 'Exempt')],
        default='full', string='Work Type')
    start_date_higri = fields.Char(string="Start Date(Higri)", required=False, compute='Gregorian2Hijri_startDate',
                                   readonly=True)
    end_date_higri = fields.Char(string="End Date(Higri)", compute='Gregorian2Hijri_endDate',
                                 readonly=True)
    check_month = fields.Integer(string='Check Month No.', compute='get_difference_months')
    fixed_bonus_ids = fields.One2many('fixed.bonus', 'contract_id', string="Bonus", track_visibility='onchange')
    total_bonus_amount = fields.Float(string="Total Bonus", compute='get_total_bonus_amount', store=True)
    other_allowance_amount = fields.Float(string='Other Allowance Amount')
    fellowship_fund = fields.Selection(selection=[('yes', 'Yes'), ('no', 'No')], string='Fellowship Fund')
    fellowship_deduction_amount = fields.Float(string='Fellowship Deduction Amount')
    total_salary = fields.Float(string='Total Salary', compute='_get_total_salary')
    other_deduction_amount = fields.Float(string='Other Deduction Amount')

    @api.depends('wage', 'housing_amount', 'transportation_amount', 'natural_work_amount', 'food_allowance_amount',
                 'mobile_allowance_amount', 'car_allowance_amount','other_allowance_amount', 'fellowship_deduction_amount', 'other_deduction_amount')
    def _get_total_salary(self):
        for rec in self:
            rec.total_salary = 0
            if rec.wage:
                rec.total_salary = (
                                           rec.wage + rec.housing_amount + rec.transportation_amount + rec.natural_work_amount + rec.food_allowance_amount + rec.food_allowance_amount + rec.mobile_allowance_amount + rec.car_allowance_amount + rec.other_allowance_amount) - rec.fellowship_deduction_amount - rec.other_deduction_amount

    @api.onchange('fellowship_fund')
    def onchange_fellowship_fund(self):
        if self.fellowship_fund != 'yes':
            self.fellowship_deduction_amount = 0.0

    def write(self, vals):
        res = super(HrContract, self).write(vals)
        if not self._context.get('skip_accommodation_check', False):
            for rec in self:
                if 'with_accommodation' in vals and vals['with_accommodation']:
                    rec.write({
                        'housing': 0,
                        'house_periodic': False,
                        'house_date': False,
                        'house_number_of_months': 0,
                        'house_allowance_type': False,
                        'transportation_allowance_type': False,
                        'transportation_amount': 0,
                        'transportation': 0,
                    })
        return res

    @api.constrains('house_number_of_months')
    def check_number_of_months(self):
        for rec in self:
            if not rec.with_accommodation and rec.house_periodic and rec.house_number_of_months <= 0:
                raise ValidationError(_('Number of months must be greater than zero.'))

    @api.depends('wage', 'transportation_allowance_type', 'house_allowance_type', 'natural_allowance_type',
                 'food_allowance_type', 'mobile_allowance_type', 'housing', 'transportation', 'natural_work',
                 'food_allowance', 'mobile_allowance', 'house_number_of_months', 'with_accommodation',
                 'car_allowance_type', 'car_allowance')
    def _get_amount(self):
        for rec in self:
            rec.housing_amount = 0
            rec.transportation_amount = 0
            rec.natural_work_amount = 0
            rec.food_allowance_amount = 0
            rec.mobile_allowance_amount = 0
            rec.car_allowance_amount = 0
            if not rec.with_accommodation:
                if rec.house_allowance_type == 'percentage':
                    if rec.wage and 100 >= rec.housing > 0 and rec.house_number_of_months > 0:
                        rec.housing_amount = (rec.wage * rec.housing) / 100 * rec.house_number_of_months
                    elif rec.wage and 100 >= rec.housing > 0 and rec.house_number_of_months < 0:
                        rec.housing_amount = (rec.wage * rec.housing) / 100
                    else:
                        rec.housing_amount = 0

                elif rec.house_allowance_type == 'amount':
                    if rec.house_number_of_months > 0 and rec.house_periodic:
                        rec.housing_amount = rec.housing * rec.house_number_of_months
                    else:
                        rec.housing_amount = rec.housing
                else:
                    rec.housing_amount = 0
                    rec.housing = 0

            if rec.transportation_allowance_type == 'percentage':
                if rec.wage and 100 >= rec.transportation > 0:
                    rec.transportation_amount = (rec.wage * rec.transportation) / 100
                else:
                    rec.transportation_amount = 0
            elif rec.transportation_allowance_type == 'amount':
                rec.transportation_amount = rec.transportation
            else:
                rec.transportation_amount = 0

            if rec.natural_allowance_type == 'percentage':
                if rec.wage and 100 >= rec.natural_work > 0:
                    rec.natural_work_amount = (rec.natural_work * rec.wage) / 100
                else:
                    rec.natural_work_amount = 0
            elif rec.natural_allowance_type == 'amount':
                rec.natural_work_amount = rec.natural_work
            else:
                rec.natural_work_amount = 0

            if rec.food_allowance_type == 'percentage':
                if rec.wage and 100 >= rec.food_allowance > 0:
                    rec.food_allowance_amount = (rec.food_allowance * rec.wage) / 100
                else:
                    rec.food_allowance_amount = 0
            elif rec.food_allowance_type == 'amount':
                rec.food_allowance_amount = rec.food_allowance
            else:
                rec.food_allowance_amount = 0

            if rec.mobile_allowance_type == 'percentage':
                if rec.wage and rec.mobile_allowance <= 100 and rec.mobile_allowance > 0:
                    rec.mobile_allowance_amount = (rec.mobile_allowance * rec.wage) / 100
                else:
                    rec.mobile_allowance_amount = 0
            elif rec.mobile_allowance_type == 'amount':
                rec.mobile_allowance_amount = rec.mobile_allowance
            else:
                rec.mobile_allowance_amount = 0

            if rec.car_allowance_type == 'percentage':
                if rec.wage and rec.car_allowance <= 100 and rec.car_allowance > 0:
                    rec.car_allowance_amount = (rec.car_allowance * rec.wage) / 100
                else:
                    rec.car_allowance_amount = 0
            elif rec.car_allowance_type == 'amount':
                rec.car_allowance_amount = rec.car_allowance
            else:
                rec.car_allowance_amount = 0

    @api.constrains('housing', 'transportation', 'natural_work', 'food_allowance', 'mobile_allowance', 'car_allowance')
    def _check_allowance_type(self):
        for rec in self:
            if rec.car_allowance_type == 'percentage':
                if rec.car_allowance <= 0:
                    raise ValidationError("Car Percentage should be greater than zero!")
                if rec.car_allowance >= 100:
                    raise ValidationError("Car Percentage should be less than 100% !!")
            if rec.house_allowance_type == 'percentage':
                if rec.housing <= 0:
                    raise ValidationError("Housing Percentage should be greater than zero!")
                if rec.housing >= 100:
                    raise ValidationError("Housing Percentage should be less than 100% !!")

            if rec.transportation_allowance_type == 'percentage':
                if rec.transportation <= 0:
                    raise ValidationError("Transportation Percentage should be greater than zero!")

                if rec.transportation >= 100:
                    raise ValidationError("Transportation Percentage should be less than 100% !!")

            if rec.natural_allowance_type == 'percentage':
                if rec.natural_work <= 0:
                    raise ValidationError("Natural work Percentage should be greater than zero!")
                if rec.natural_work >= 100:
                    raise ValidationError("Natural work Percentage should be less than 100% !!")

            if rec.food_allowance_type == 'percentage':
                if rec.food_allowance <= 0:
                    raise ValidationError("Food Percentage should be greater than zero!")
                if rec.food_allowance >= 100:
                    raise ValidationError("Food Percentage should be less than 100% !!")

            if rec.mobile_allowance_type == 'percentage':
                if rec.mobile_allowance <= 0:
                    raise ValidationError("Mobile Percentage should be greater than zero!")
                if rec.mobile_allowance >= 100:
                    raise ValidationError("Mobile Percentage should be less than 100% !!")

    @api.onchange('contract_period', 'date_start')
    def get_contract_end_date(self):
        for rec in self:
            if rec.date_start:
                start_date = fields.Date.from_string(rec.date_start)
                contract_year = start_date.year
                if rec.contract_period == 'one_year':
                    rec.date_end = start_date.replace(year=contract_year + 1)
                elif rec.contract_period == 'three_month':
                    rec.date_end = start_date + relativedelta(months=+3)
                elif rec.contract_period == 'six_month':
                    rec.date_end = start_date + relativedelta(months=+6)
                elif rec.contract_period == 'two_year':
                    rec.date_end = start_date.replace(year=contract_year + 2)
                else:
                    apply_years = 60 - int(rec.employee_id.age)
                    rec.date_end = start_date + relativedelta(years=+apply_years)

    @api.onchange('transportation_allowance_type')
    def clear_transportation_value(self):
        for rec in self:
            rec.transportation = 0

    @api.onchange('house_allowance_type')
    def clear_housing_value(self):
        for rec in self:
            rec.housing = 0

    @api.onchange('natural_allowance_type')
    def clear_natural_work_value(self):
        for rec in self:
            rec.natural_work = 0

    @api.onchange('food_allowance_type')
    def clear_food_value(self):
        for rec in self:
            rec.food_allowance = 0

    @api.onchange('mobile_allowance_type')
    def clear_mobile_value(self):
        for rec in self:
            rec.mobile_allowance = 0

    @api.onchange('car_allowance_type')
    def clear_car_value(self):
        for rec in self:
            rec.car_allowance = 0

    @api.depends('fixed_bonus_ids')
    def get_total_bonus_amount(self):
        for rec in self:
            rec.total_bonus_amount = sum([bonus_line.bonus_amount for bonus_line in rec.fixed_bonus_ids])

    def intPart(self, floatNum):
        if floatNum < -0.0000001: return math.ceil(floatNum - 0.0000001)
        return math.floor(floatNum + 0.0000001)

    @api.depends('date_end')
    def Gregorian2Hijri_endDate(self):
        if self.date_end:
            year = fields.datetime.strptime(str(self.date_end), '%Y-%m-%d').year
            month = fields.datetime.strptime(str(self.date_end), '%Y-%m-%d').month
            day = fields.datetime.strptime(str(self.date_end), '%Y-%m-%d').day
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
            self.end_date_higri = " %s  %s  %s " % (month_map[m]['name'], d, y)
        else:
            self.end_date_higri = ""

    @api.depends('date_start')
    def Gregorian2Hijri_startDate(self):
        if self.date_start:
            year = fields.datetime.strptime(str(self.date_start), '%Y-%m-%d').year
            month = fields.datetime.strptime(str(self.date_start), '%Y-%m-%d').month
            day = fields.datetime.strptime(str(self.date_start), '%Y-%m-%d').day
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
            self.start_date_higri = " %s  %s  %s " % (d, month_map[m]['name'], y)
        else:
            self.start_date_higri = ""

    @api.constrains("wage")
    def check_wage(self):
        for rec in self:
            if not rec.wage:
                raise ValidationError("Wage must be more than Zero")

    def get_contract_period_length(self, lang):
        for rec in self:
            if rec.date_start and rec.date_end:
                date_start = fields.Date.from_string(str(rec.date_start))
                date_end = fields.Date.from_string(str(rec.date_end))
                years = relativedelta(date_end, date_start).years * 365
                month = relativedelta(date_end, date_start).months * 30
                days = relativedelta(date_end, date_start).days
                result = float(years) + float(month) + float(days)
                result = str(round(float(result / float(365)), 3))
                nu, dec = result.split('.')
                nu = int(nu)
                dec = int(dec[:1])
                result = str(nu) + '.' + str(dec)
                words = num2words(int(float(result)), lang)
                words = words.replace('point zero', '')
                return words

    @api.onchange('date_end')
    def get_difference_months(self):
        for rec in self:
            if rec.date_end:
                current_date = fields.Date.from_string(fields.Date.today())
                end_date = fields.Date.from_string(rec.date_end)
                rec.check_month = (end_date.year - current_date.year) * 12 + end_date.month - current_date.month
            else:
                rec.check_month = 0
