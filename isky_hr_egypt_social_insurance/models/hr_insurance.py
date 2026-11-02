# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrInsurance(models.Model):
    _name = 'hr.insurance'
    _rec_name = 'insurance_sequence'
    _description = 'HR Insurance'

    state = fields.Selection([('draft', "Draft"), ('submitted', "Submitted")], default='draft', string="Status")
    insurance_line_ids = fields.One2many('insurance.line', 'insurance_id', copy=True)
    insurance_sequence = fields.Char(string='Sequence')
    insurance_date = fields.Date(string='Insurance Date', default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    total_insurance = fields.Float('Total Insurance', compute='_get_total_insurance')

    @api.depends('insurance_line_ids')
    def _get_total_insurance(self):
        for rec in self:
            rec.total_insurance = sum(line.total_insurance for line in rec.insurance_line_ids)

    @api.model
    def create(self,vals):
        if vals:
            vals['insurance_sequence'] = self.env['ir.sequence'].next_by_code('hr.insurance.sequence')
        return super(HrInsurance, self).create(vals)

    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = 'draft'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError("Only Draft Insurance Can Be Deleted!")
            else:
                return super(HrInsurance, self).unlink()
