# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class HrContract(models.Model):
    _inherit = "hr.contract"

    probation_period = fields.Selection(selection=[('one_month', 'One Month'),
                                                   ('two_months', 'Two Months'),
                                                   ('three_months', 'Three Months'),
                                                   ('six_months', 'Six Months'),
                                                   ('no_probation_period', 'No Probation Period')],
                                        default='one_month', string='Probation period')
    work_location_id = fields.Many2one('hr.work.location', string="Work Location")
