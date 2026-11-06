# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BrokerVisit(models.Model):
    _name = 'broker.visit'
    _description = 'Broker Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(
        string='Visit Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    broker_id = fields.Many2one(
        'res.partner',
        string='Broker',
        required=True,
        domain=[('is_broker', '=', True)],
        tracking=True
    )
    visit_date = fields.Date(
        string='Visit Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    check_in_datetime = fields.Datetime(
        string='Check-in Time',
        readonly=True,
        tracking=True
    )
    check_out_datetime = fields.Datetime(
        string='Check-out Time',
        readonly=True,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out')
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True)

    comment_ids = fields.One2many(
        'broker.visit.comment',
        'visit_id',
        string='Comment Lines'
    )
    location_attachment = fields.Binary("Location Attachment")

    def action_check_in(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("You can only check in from the Draft state."))
        if self.check_in_datetime:
            raise UserError(_("Already checked in."))
        self.write({
            'check_in_datetime': fields.Datetime.now(),
            'state': 'checked_in'
        })

    def action_check_out(self):
        self.ensure_one()
        if self.state != 'checked_in':
            raise UserError(_("You can only check out from the Checked In state."))
        if not self.check_in_datetime:
            raise UserError(_("You must check in first before checking out."))
        if self.check_out_datetime:
            raise UserError(_("Already checked out."))
        self.write({
            'check_out_datetime': fields.Datetime.now(),
            'state': 'checked_out'
        })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('broker.visit') or _('New')
        return super(BrokerVisit, self).create(vals_list)


class BrokerVisitComment(models.Model):
    _name = 'broker.visit.comment'
    _description = 'Broker Visit Comment'
    _order = 'date desc, id desc'

    visit_id = fields.Many2one(
        'broker.visit',
        string='Broker Visit',
        required=True,
        ondelete='cascade'
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True,
        required=True
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
        required=True
    )
    comment = fields.Text(
        string='Comment',
        required=True
    )
