# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    executive_committee_employee_id = fields.Many2one('hr.employee', string='Executive Committee Employee')
