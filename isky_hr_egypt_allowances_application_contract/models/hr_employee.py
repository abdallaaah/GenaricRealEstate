# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    is_egyptian = fields.Boolean(string='Egyptian', related='country_id.is_egypt', store=True)
    iqama_issue_date = fields.Date(string='Iqama Issue Date')
    iqama_expiry_date = fields.Date(string='Iqama Expiry Date')
    iqama_number = fields.Char(string="Iqama Number")
    iqama_issue_place = fields.Many2one('res.country', string='Iqama Issue Place')
    contract_period = fields.Selection(selection=[('one', 'One Year'), ('two', 'Two Years')], string="Contract Period")