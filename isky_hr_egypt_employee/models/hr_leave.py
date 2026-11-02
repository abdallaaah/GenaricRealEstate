# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    work_location_id = fields.Many2one('hr.work.location',string="Work Location")
