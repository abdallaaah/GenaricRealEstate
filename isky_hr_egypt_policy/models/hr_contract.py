# -*- coding: utf-8 -*-
from odoo import models, fields


class HrContract(models.Model):
    _inherit = "hr.contract"

    employee_policy_id = fields.Many2one('policy.group', string='Policy Group')
    social_insurance_amount = fields.Float(string='Social Insurance')

