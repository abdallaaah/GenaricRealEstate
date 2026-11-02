# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    insurance_number = fields.Char('Insurance Number')
    insurance_office = fields.Char("Insurance Office")
    insurance_office_zone = fields.Char("Insurance Office Zone")
    owner = fields.Many2one('res.users', string='Owner/Manager')
    start_date = fields.Date(string='Business Start Date')

