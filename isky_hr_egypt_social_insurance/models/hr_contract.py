# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PolicyGroup(models.Model):
    _inherit = 'policy.group'

    insurance_policy_id = fields.Many2one('insurance.policy', string='Insurance Policy')


class HrContract(models.Model):
    _inherit = 'hr.contract'

    si_position_id = fields.Many2one('si.position', string="Position At SI")
    si_status_id = fields.Many2one('insurance.status', string="Status")
    si_type_id = fields.Many2one('insurance.type', string="Type")
    si_number = fields.Char(string="Number")
    si_org_number = fields.Char(string="Social Org. Number")
    si_area = fields.Char(string='Area', translate=True)
    si_office = fields.Char(string='Office', translate=True)
    insurance_line_ids = fields.One2many('insurance.line', 'contract_id', string='Insurance Data')
    social_insurance_amount = fields.Float(string='Social Insurance', compute='calc_social_insurance_amount')
    company_social_insurance_amount = fields.Float(string='Company Social Insurance', compute='calc_social_insurance_amount')
    social_insurance_open_balance = fields.Float(
        string='Opening Balance',
        required=False)

    @api.depends('employee_id', 'insurance_line_ids')
    def calc_social_insurance_amount(self):
        for contract in self:
            contract.social_insurance_amount = 0.0
            contract.company_social_insurance_amount = 0.0
            if contract.employee_id and contract.insurance_line_ids:
                insurance_lines = contract.insurance_line_ids.filtered(lambda line: line.state == 'submitted')
                contract.social_insurance_amount = insurance_lines[
                    len(insurance_lines) - 1].total_employee_insurance if insurance_lines else 0.0
                contract.company_social_insurance_amount = insurance_lines[
                    len(insurance_lines) - 1].total_company_insurance if insurance_lines else 0.0
