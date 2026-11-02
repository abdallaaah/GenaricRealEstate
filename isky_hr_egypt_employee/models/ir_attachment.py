# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    employee_id = fields.Many2one('hr.employee', string='Employee')
    filename = fields.Char()
