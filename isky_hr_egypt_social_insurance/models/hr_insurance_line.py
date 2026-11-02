# -*- coding: utf-8 -*-

from odoo import fields, models, api


class InsuranceLine(models.Model):
    _name = "insurance.line"
    _rec_name = 'employee_id'
    _order = 'insurance_date asc'
    _description = 'Insurance Line'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    contract_id = fields.Many2one('hr.contract', related='employee_id.contract_id', string="Contract")
    wage = fields.Monetary(related='contract_id.wage', string="Wage")
    insurance_policy_id = fields.Many2one('insurance.policy',
                                          related='contract_id.employee_policy_id.insurance_policy_id',
                                          string='Insurance Policy',store=1)
    insurance_date = fields.Date(string='Insurance Date', default=fields.Date.context_today, )
    insurance_id = fields.Many2one('hr.insurance', string='Insurance', ondelete='cascade')
    state = fields.Selection([('draft', "Draft"), ('submitted', "Submitted")], related='insurance_id.state',
                             default='draft', string="Status", )

    si_position_id = fields.Many2one('si.position', string="Position At SI", compute='get_si_position_id')
    si_number = fields.Char(string="Number", compute='get_si_number')
    subscription = fields.Float(string='Subscription')
    total_employee_insurance = fields.Float(string='Total Employee', compute='get_insurance_values', readonly=1,
                                            store=True)
    total_company_insurance = fields.Float(string='Total Company', compute='get_insurance_values', readonly=1,
                                           store=True)
    total_insurance = fields.Float(string='Total Insurance', compute='get_insurance_values', readonly=1, store=True)
    insurance_per_day = fields.Float(string='Insurance Per Day', compute='get_insurance_values', readonly=1, store=True)
    fixed_amount = fields.Boolean(string='Fixed?', compute='check_insurance')
    salary_rule_ids = fields.Many2many('hr.salary.rule', string='Rules', compute='check_insurance')
    rules_amount = fields.Float(string='Total Allowances', compute='calc_total_allowances')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(string="Currency", related='company_id.currency_id', readonly=True)

    @api.depends('employee_id')
    def check_insurance(self):
        for policy in self:
            policy.fixed_amount = True
            policy.salary_rule_ids = False
            if policy.employee_id and policy.employee_id.contract_id and policy.employee_id.contract_id.employee_policy_id and policy.employee_id.contract_id.employee_policy_id.insurance_policy_id:
                policy.fixed_amount = policy.employee_id.contract_id.employee_policy_id.insurance_policy_id.fixed_amount
                policy.salary_rule_ids = policy.employee_id.contract_id.employee_policy_id.insurance_policy_id.salary_rule_ids.ids

    @api.depends('salary_rule_ids', 'employee_id')
    def calc_total_allowances(self):
        for policy in self:
            policy.rules_amount = 0.0
            if policy.salary_rule_ids and policy.employee_id and policy.employee_id.contract_id:
                for rule in policy.salary_rule_ids:
                    python_code = rule.amount_python_compute
                    allowance_name = python_code[python_code.index('.') + 1:]
                    policy.rules_amount += getattr(policy.employee_id.contract_id, allowance_name)

    @api.depends('contract_id', 'subscription', 'rules_amount')
    def get_insurance_values(self):
        for record in self:
            record.total_employee_insurance = 0.0
            record.total_company_insurance = 0.0
            record.total_insurance = 0.0
            record.insurance_per_day = 0.0

            if record.fixed_amount and record.subscription and record.employee_id and record.contract_id and record.employee_id.contract_id.employee_policy_id.insurance_policy_id:
                record.total_employee_insurance = record.subscription * record.contract_id.employee_policy_id.insurance_policy_id.employee_percentage / 100.0
                record.total_company_insurance = record.subscription * record.contract_id.employee_policy_id.insurance_policy_id.company_percentage / 100.0
                record.total_insurance = record.total_company_insurance + record.total_employee_insurance
                record.insurance_per_day = round((record.subscription / 30.0), 2)
            elif not record.fixed_amount and record.rules_amount and record.employee_id and record.employee_id.contract_id and record.employee_id.contract_id.employee_policy_id and record.employee_id.contract_id.employee_policy_id.insurance_policy_id:
                record.total_employee_insurance = record.rules_amount * record.contract_id.employee_policy_id.insurance_policy_id.employee_percentage / 100.0
                record.total_company_insurance = record.rules_amount * record.contract_id.employee_policy_id.insurance_policy_id.company_percentage / 100.0
                record.total_insurance = record.total_company_insurance + record.total_employee_insurance
                record.insurance_per_day = round((record.rules_amount / 30.0), 2)

    @api.depends('employee_id')
    def get_si_number(self):
        for record in self:
            record.si_number = ''
            if record.employee_id and record.employee_id.contract_id and record.employee_id.contract_id.si_number:
                record.si_number = record.employee_id.contract_id.si_number

    @api.depends('employee_id')
    def get_si_position_id(self):
        for record in self:
            record.si_position_id = False
            if record.employee_id and record.employee_id.contract_id and record.employee_id.contract_id.si_position_id:
                record.si_position_id = record.employee_id.contract_id.si_position_id.id
