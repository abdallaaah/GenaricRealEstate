# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FixedBonus(models.Model):
    _name = "fixed.bonus"
    _description = 'Fixed Bouns'
    _rec_name = 'bonus_type_id'
    _inherit = ['mail.thread']

    bonus_amount = fields.Float(string='Amount', track_visibility='onchange')
    bonus_type_id = fields.Many2one('fixed.bonus.type', string='Type', required=1, track_visibility='onchange')
    contract_id = fields.Many2one('hr.contract', string="Bonus")
