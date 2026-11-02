# -*- coding: utf-8 -*-
from odoo import models, fields, api
import calendar


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    number_of_days = fields.Float(string='Number of Days', digits=(16, 3))


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    employee_policy_id = fields.Many2one('policy.group', string='Policy Group')
    social_insurance_amount = fields.Float(string='Social Insurance', related='contract_id.social_insurance_amount')

    def get_rate_from_payslip_dates(self, date_from_string, date_to_string):
        for payslip in self:
            diff_days = new_rate = 0
            from_date = fields.Datetime.from_string(date_from_string).date()
            to_date = fields.Datetime.from_string(date_to_string).date()
            from_month_range = calendar.monthrange(from_date.year, from_date.month)
            to_month_range = calendar.monthrange(to_date.year, to_date.month)

            # two dates in same month
            if from_date.month == to_date.month:
                if from_month_range[1] < 30:
                    diff_days_in_feb_month = 30 - from_month_range[1]
                    if to_date.day != from_month_range[1]:
                        diff_days = (to_date - from_date).days + 1
                    elif to_date.day == from_month_range[1]:
                        diff_days = (to_date - from_date).days + 1 + diff_days_in_feb_month

                elif from_month_range[1] > 30:
                    diff_days = (to_date - from_date).days
                elif from_month_range[1] == 30:
                    diff_days = (to_date - from_date).days + 1

                new_rate = round((float(diff_days) / 30), 5)

            # two dates not in same month
            elif from_date.month != to_date.month:
                # feb month in payslip date to
                if from_month_range[1] >= 30 and to_month_range[1] < 30:
                    if from_date.day == 31:
                        if to_date.day != to_month_range[1]:
                            diff_days = (to_date - from_date).days
                        elif to_date.day == to_month_range[1]:
                            diff_days_in_feb_month = 30 - to_month_range[1]
                            diff_days = (to_date - from_date).days + diff_days_in_feb_month

                    elif from_date.day == 30:
                        if to_date.day != to_month_range[1]:
                            diff_days = (to_date - from_date).days + 1
                        elif to_date.day == to_month_range[1]:
                            diff_days_in_feb_month = 30 - to_month_range[1]
                            diff_days = (to_date - from_date).days + 1 + diff_days_in_feb_month
                    elif to_month_range[1] < 30:
                        if (to_date - from_date).days > 30:
                            diff_days = (to_date - from_date).days - (30 - to_month_range[1])
                        else:
                            diff_days = (to_date - from_date).days
                    else:
                        diff_days = (to_date - from_date).days + 1

                # feb month in payslip date from
                elif to_month_range[1] >= 30 and from_month_range[1] < 30:
                    diff_days_in_feb_month = 30 - from_month_range[1]
                    if to_date.day == 31:
                        diff_days = (to_date - from_date).days + diff_days_in_feb_month
                    else:
                        diff_days = (to_date - from_date).days + diff_days_in_feb_month + 1

                elif from_month_range[1] == 31 and to_month_range[1] == 30:
                    diff_days = (to_date - from_date).days

                elif from_month_range[1] == 30 and to_month_range[1] == 31:
                    if to_date.day != to_month_range[1]:
                        diff_days = (to_date - from_date).days + 1
                    else:
                        diff_days = (to_date - from_date).days
                else:
                    diff_days = (to_date - from_date).days
                new_rate = round(float(diff_days / 30), 5)
            return new_rate
