# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WorkPermit(models.Model):
    _name = 'work.permit'
    _description = 'Work Permit'

    name = fields.Char(string='Work Permit No.', required=1, translate=True)
    payment_no = fields.Char(string='Payment No.')
    issued_date = fields.Date(string='Issued Date')
    expiry_date = fields.Date(string='Expiry Date')
    amount = fields.Float(string='Amount')
    employee_id = fields.Many2one('hr.employee', string='Employee')

    @api.constrains('issued_date', 'expiry_date')
    def check_dates(self):
        for rec in self:
            if rec.issued_date and rec.expiry_date:
                if rec.expiry_date < rec.issued_date:
                    raise ValidationError(_('Expiry date must be larger than issued date in work permit.'))
