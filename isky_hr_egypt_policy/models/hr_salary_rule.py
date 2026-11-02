# -*- coding: utf-8 -*-
from odoo import models, fields


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    type = fields.Selection(
        [('basic', 'Basic'), ('overtime', 'Overtime'), ('days_off', 'Days Off'), ('housing', 'Housing'),
         ('transportation', 'Transportation'), ('tickets', 'Tickets'), ('food', 'Food'), ('mobile', 'Mobile'),
         ('natural_work', 'Natural Work'), ('other_dues', 'Other Dues'),
         ('bonus', 'Other Bonus'), ('fixed_bonus', 'Bonus'), ('miscellaneous', 'Miscellaneous'), ('car', 'Car'),
         ('complementary', 'Complementary'), ('annual_increase', 'Annual Increase'), ('gross', 'Gross'),
         ('insurance', 'Insurance'), ('mandate', 'Mandate'),
         ('late_attendance', 'Late Attendance'), ('gosi', 'GOSI'), ('absence', 'Absence'), ('loan', 'Loan'),
         ('salary_advance', 'Salary Advance'), ('medical_insurance', 'Medical Insurance'),
         ('other_deduction', 'Other Deduction'), ('unpaid_leaves', 'Unpaid Leaves'),
         ('employee_behavior', 'Employee Behavior'), ('work_organization', 'Work Organization'), ('sundry', 'Sundry'),
         ('net', 'Net'), ('eos', 'EOS'), ('leaves', 'Leaves')])
