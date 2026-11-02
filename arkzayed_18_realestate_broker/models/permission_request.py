# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PermissionRequest(models.Model):
    _name = 'permission.request'
    _description = 'Permission Request'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    requester_id = fields.Many2one('res.users', string='Requester',default=lambda self: self.env.user,readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', related='requester_id.sale_team_id', store=True)
    request_type = fields.Selection([
        ('lead', 'Lead'),
        ('unit', 'Unit')
    ], string='Request Type')
    client_name = fields.Char(string='Client Name')
    client_number = fields.Char(string='Client Number')
    create_date = fields.Datetime(string='Creation Date', readonly=True)
    approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Approval Status', default='pending')
    request_details = fields.Text(string='Request Details')
    operations_feedback = fields.Text(string='Operations Feedback')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('permission.request') or _('New')
        return super(PermissionRequest, self).create(vals_list)

    def action_approve(self):
        for record in self:
            record.approval_status = 'approved'

    def action_reject(self):
        for record in self:
            record.approval_status = 'rejected'
