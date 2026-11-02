# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError
from datetime import datetime
import time
import babel
from dateutil.relativedelta import relativedelta


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.constrains('employee_id', 'contract_id', 'date_from', 'date_to','state')
    def prevent_duplicate_payslip(self):
        for rec in self:
            if rec.employee_id and rec.date_from and rec.date_to:
                ttyme = datetime.fromtimestamp(time.mktime(time.strptime(str(rec.date_to), "%Y-%m-%d")))
                locale = self.env.context.get('lang') or 'en_US'
                rec.name = _('Salary Slip of %s for %s') % (
                    rec.employee_id.name,
                    tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
            if rec.employee_id and rec.contract_id and rec.date_from and rec.date_to:
                payslip_records = self.env['hr.payslip'].search(
                    [('employee_id', '=', rec.employee_id.id), ('contract_id', '=', rec.contract_id.id),
                     ('date_from', '>=', rec.date_from), ('date_to', '<=', rec.date_to), ('state', '=', 'done')])

                if len(payslip_records) > 1:
                    raise ValidationError(
                        _('Sorry .. this employee has a confirmed payslip with same contract in this period'))

    def compute_sheet(self):
        res = super(HrPayslip, self).compute_sheet()
        for rec in self:
            housing_rule_objects = self.env['hr.salary.rule'].search([('type', '=', 'housing')])
            for payslip_line in rec.line_ids:
                if rec.contract_id.house_periodic and rec.contract_id.house_date and not rec.contract_id.with_accommodation:
                    for house_rule in housing_rule_objects:
                        if payslip_line.salary_rule_id.id == house_rule.id:
                            if rec.date_from <= rec.contract_id.house_date <= rec.date_to:
                                if rec.contract_id.house_number_of_months > 0:
                                    payslip_line.total = payslip_line.total
                            else:
                                payslip_line.total = 0
                                payslip_line.amount = 0
                                payslip_line.quantity = 0

        return res

    def action_payslip_done(self):
        res = super(HrPayslip, self).action_payslip_done()
        for rec in self:
            # periodic house and promotion
            housing_rule_objects = self.env['hr.salary.rule'].search([('type', '=', 'housing')])
            for payslip_line in rec.line_ids:
                # check periodic_rules
                # house
                if rec.contract_id.house_periodic and rec.contract_id.house_date and not rec.contract_id.with_accommodation:
                    for house_rule in housing_rule_objects:
                        if payslip_line.salary_rule_id.id == house_rule.id:
                            if rec.date_from <= rec.contract_id.house_date <= rec.date_to:
                                house_date = fields.Date.from_string(str(rec.contract_id.house_date))
                                next_house_date = house_date + relativedelta(
                                    months=+rec.contract_id.house_number_of_months)
                                next_date_house = fields.Date.from_string(str(next_house_date))
                                rec.contract_id.house_date = next_date_house

        return res
