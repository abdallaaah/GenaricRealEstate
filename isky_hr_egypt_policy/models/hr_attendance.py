# -*- coding: utf-8 -*-

from odoo import models, fields, api
from pytz import timezone


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    emp_check_in_date = fields.Date(string='Check-in Date', compute="get_emp_check_date", store=True)
    emp_check_out_date = fields.Date(string='Check-out Date', compute="get_emp_check_date", store=True)

    @api.depends('check_in', 'check_out', 'employee_id')
    def get_emp_check_date(self):
        for rec in self:
            rec.emp_check_out_date = False
            rec.emp_check_in_date = False
            if rec.employee_id and rec.employee_id.contract_id:
                calendar = rec.employee_id.contract_id.resource_calendar_id
                tz = timezone(calendar.tz)
                if rec.check_in:
                    rec.emp_check_in_date = rec.check_in.astimezone(tz).date()
                if rec.check_out:
                    rec.emp_check_out_date = rec.check_out.astimezone(tz).date()
            else:
                if rec.check_in:
                    rec.emp_check_in_date = rec.check_in.date()
                if rec.check_out:
                    rec.emp_check_out_date = rec.check_out.date()