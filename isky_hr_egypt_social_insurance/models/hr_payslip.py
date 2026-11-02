# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    social_insurance_amount = fields.Float(string='Social Insurance', related='contract_id.social_insurance_amount')
